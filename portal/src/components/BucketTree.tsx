import { useCallback, useEffect, useMemo, useState } from "react";
import { App, Button, Input, Modal, Tooltip, Tree } from "antd";
import { Database, Files, Folder, Trash2 } from "lucide-react";
import type { DataNode } from "antd/es/tree";
import * as api from "../api/client";
import { useI18n } from "../i18n";

interface Props {
  config: api.ClientConfig;
  bucket: string;
  prefix: string;
  onSelect: (bucket: string, prefix: string) => void;
  onConfigRefresh: () => Promise<void>;
}

const FOLDER_SCAN_LIMIT = 100;
const FOLDER_SCAN_PAGES = 6;

interface TreeFolder extends DataNode {
  children?: TreeFolder[];
}

function buildTree(
  buckets: string[],
  allLabel: string,
  renderBucketTitle: (name: string) => React.ReactNode,
  bucketHasFiles: Record<string, boolean>,
): TreeFolder[] {
  return [
    { key: "", title: allLabel, icon: <Files size={14} />, isLeaf: true },
    ...buckets.map((name) => ({
      key: name,
      title: renderBucketTitle(name),
      icon: (
        <Database
          size={14}
          className={bucketHasFiles[name] ? "bucket-icon bucket-icon-nonempty" : "bucket-icon bucket-icon-empty"}
        />
      ),
      isLeaf: false,
    })),
  ];
}

function splitNodeKey(key: string): [string, string] {
  if (key === "") {
    return ["", ""];
  }
  const slash = key.indexOf("/");
  if (slash === -1) {
    return [key, ""];
  }
  return [key.slice(0, slash), key.slice(slash + 1)];
}

function withChildren(nodes: TreeFolder[], key: string, children: TreeFolder[]): TreeFolder[] {
  return nodes.map((node) => {
    if (node.key === key) {
      return { ...node, children };
    }
    if (node.children) {
      return { ...node, children: withChildren(node.children, key, children) };
    }
    return node;
  });
}

async function collectFolders(bucket: string, prefix: string): Promise<string[]> {
  const seen = new Set<string>();
  let offset = 0;
  for (let page = 0; page < FOLDER_SCAN_PAGES; page += 1) {
    const result = await api.listFiles({
      bucket,
      prefix: prefix || undefined,
      limit: FOLDER_SCAN_LIMIT,
      offset,
      sortBy: "name",
    });
    for (const item of result.items) {
      const rest = item.object_key.slice(prefix.length);
      const slash = rest.indexOf("/");
      if (slash > 0) {
        seen.add(rest.slice(0, slash + 1));
      }
    }
    if (result.offset + result.items.length >= result.total) {
      break;
    }
    offset += result.items.length;
  }
  return Array.from(seen).sort();
}

export function BucketTree({ config, bucket, prefix, onSelect, onConfigRefresh }: Props) {
  const { t } = useI18n();
  const { message: messageApi } = App.useApp();
  const managed = useMemo(
    () => new Set(config.uploads.managed_buckets ?? []),
    [config.uploads.managed_buckets],
  );
  const [treeData, setTreeData] = useState<TreeFolder[]>([]);
  const [bucketHasFiles, setBucketHasFiles] = useState<Record<string, boolean>>({});
  const [selectedKey, setSelectedKey] = useState("");
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [loadingKeys, setLoadingKeys] = useState<React.Key[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  const renderBucketTitle = useCallback(
    (name: string) => (
      <span className="bucket-node">
        <span className="bucket-node-name">{name}</span>
        {managed.has(name) && (
          <Tooltip title={t("tree.deleteBucket")}>
            <Button
              type="text"
              size="small"
              className="bucket-delete-btn"
              icon={<Trash2 size={13} />}
              onClick={(event) => {
                event.stopPropagation();
                event.preventDefault();
                setDeleteTarget(name);
                setConfirmText("");
              }}
            />
          </Tooltip>
        )}
      </span>
    ),
    [managed, t],
  );

  // 桶列表变化（新建桶后刷新配置）时重建根节点。
  useEffect(() => {
    setTreeData(
      buildTree(config.uploads.allowed_buckets, t("tree.all"), renderBucketTitle, bucketHasFiles),
    );
  }, [config.uploads.allowed_buckets, t, renderBucketTitle, bucketHasFiles]);

  // 查询各桶是否已有文件（active 对象），用于图标着色区分。
  useEffect(() => {
    let cancelled = false;
    const buckets = config.uploads.allowed_buckets;
    setBucketHasFiles({});
    void Promise.all(
      buckets.map(async (name) => {
        try {
          const result = await api.listFiles({ bucket: name, status: "active", limit: 1 });
          return [name, result.total > 0] as const;
        } catch {
          return [name, false] as const;
        }
      }),
    ).then((entries) => {
      if (!cancelled) {
        setBucketHasFiles(Object.fromEntries(entries));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [config.uploads.allowed_buckets]);

  // 外部（前缀输入框等）改动筛选条件时同步选中态。
  useEffect(() => {
    setSelectedKey(bucket ? (prefix ? `${bucket}/${prefix}` : bucket) : "");
  }, [bucket, prefix]);

  const handleSelect = useCallback(
    (keys: React.Key[]) => {
      const key = keys.length > 0 ? String(keys[0]) : "";
      if (key === "") {
        onSelect("", "");
        return;
      }
      const [nodeBucket, nodePrefix] = splitNodeKey(key);
      onSelect(nodeBucket, nodePrefix);
    },
    [onSelect],
  );

  const handleExpand = useCallback(
    async (keys: React.Key[], info: { expanded: boolean; node: { key: React.Key } }) => {
      const key = String(info.node.key);
      setExpandedKeys(keys);
      if (!info.expanded || key === "" || loadingKeys.includes(key)) {
        return;
      }
      const [nodeBucket, nodePrefix] = splitNodeKey(key);
      if (!nodeBucket) {
        return;
      }
      const findNode = (nodes: TreeFolder[]): TreeFolder | undefined => {
        for (const node of nodes) {
          if (node.key === key) {
            return node;
          }
          if (node.children) {
            const found = findNode(node.children);
            if (found) {
              return found;
            }
          }
        }
        return undefined;
      };
      if (findNode(treeData)?.children) {
        return;
      }
      setLoadingKeys((prev) => [...prev, key]);
      try {
        const folders = await collectFolders(nodeBucket, nodePrefix);
        const children: TreeFolder[] = folders.map((folder) => ({
          key: key === nodeBucket ? `${nodeBucket}/${folder}` : `${key}/${folder}`,
          title: folder.replace(/\/$/, ""),
          icon: <Folder size={14} />,
          isLeaf: false,
        }));
        setTreeData((prev) => withChildren(prev, key, children));
      } catch {
        // Ignore: the node simply stays without children.
      } finally {
        setLoadingKeys((prev) => prev.filter((item) => item !== key));
      }
    },
    [treeData, loadingKeys],
  );

  const closeDelete = useCallback(() => {
    if (!deleting) {
      setDeleteTarget(null);
      setConfirmText("");
    }
  }, [deleting]);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteBucket(deleteTarget);
      messageApi.success(t("bucket.deleted", { name: deleteTarget }));
      setDeleteTarget(null);
      setConfirmText("");
      if (bucket === deleteTarget) {
        onSelect("", "");
      }
      await onConfigRefresh();
    } catch (err) {
      const code = err instanceof Error ? err.message : String(err);
      if (code === "BUCKET_NOT_EMPTY") {
        messageApi.error(t("bucket.notEmpty", { name: deleteTarget }));
      } else if (code === "BUCKET_NOT_DELETABLE") {
        messageApi.error(t("bucket.notDeletable", { name: deleteTarget }));
      } else if (code === "BUCKET_NOT_FOUND") {
        messageApi.error(t("bucket.notFound", { name: deleteTarget }));
      } else {
        messageApi.error(t("bucket.deleteFailed", { msg: code }));
      }
    } finally {
      setDeleting(false);
    }
  }, [bucket, deleteTarget, messageApi, onConfigRefresh, onSelect, t]);

  return (
    <>
      <Tree
        showIcon
        blockNode
        treeData={treeData}
        selectedKeys={selectedKey ? [selectedKey] : []}
        expandedKeys={expandedKeys}
        onExpand={handleExpand}
        onSelect={handleSelect}
      />
      <Modal
        title={t("bucket.deleteTitle")}
        open={deleteTarget !== null}
        onOk={() => void handleDelete()}
        confirmLoading={deleting}
        onCancel={closeDelete}
        okText={t("common.delete")}
        okButtonProps={{ danger: true, disabled: confirmText !== deleteTarget }}
        cancelText={t("common.cancel")}
        destroyOnHidden
      >
        <p className="form-hint">{t("bucket.deleteConfirm", { name: deleteTarget ?? "" })}</p>
        <Input
          value={confirmText}
          onChange={(event) => setConfirmText(event.target.value)}
          onPressEnter={() => {
            if (confirmText === deleteTarget) {
              void handleDelete();
            }
          }}
          placeholder={t("bucket.deletePlaceholder")}
          autoFocus
        />
        <div className="form-hint">{t("bucket.deleteHint", { name: deleteTarget ?? "" })}</div>
      </Modal>
    </>
  );
}
