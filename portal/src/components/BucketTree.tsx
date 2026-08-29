import { useCallback, useEffect, useState } from "react";
import { Tree } from "antd";
import { Database, Files, Folder } from "lucide-react";
import type { DataNode } from "antd/es/tree";
import * as api from "../api/client";

interface Props {
  config: api.ClientConfig;
  bucket: string;
  prefix: string;
  onSelect: (bucket: string, prefix: string) => void;
}

const FOLDER_SCAN_LIMIT = 100;
const FOLDER_SCAN_PAGES = 6;

interface TreeFolder extends DataNode {
  children?: TreeFolder[];
}

function buildTree(buckets: string[]): TreeFolder[] {
  return [
    { key: "", title: "全部文件", icon: <Files size={14} />, isLeaf: true },
    ...buckets.map((name) => ({
      key: name,
      title: name,
      icon: <Database size={14} />,
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

export function BucketTree({ config, bucket, prefix, onSelect }: Props) {
  const [treeData, setTreeData] = useState<TreeFolder[]>(() =>
    buildTree(config.uploads.allowed_buckets),
  );
  const [selectedKey, setSelectedKey] = useState("");
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [loadingKeys, setLoadingKeys] = useState<React.Key[]>([]);

  // 桶列表变化（新建桶后刷新配置）时重建根节点。
  useEffect(() => {
    setTreeData(buildTree(config.uploads.allowed_buckets));
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

  return (
    <Tree
      showIcon
      blockNode
      treeData={treeData}
      selectedKeys={selectedKey ? [selectedKey] : []}
      expandedKeys={expandedKeys}
      onExpand={handleExpand}
      onSelect={handleSelect}
    />
  );
}
