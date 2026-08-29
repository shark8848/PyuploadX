import { useCallback, useState } from "react";
import { CloudUpload } from "lucide-react";
import { useI18n } from "../i18n";

interface Props {
  onFiles: (files: FileList) => void;
  multiple?: boolean;
  directory?: boolean;
  disabled?: boolean;
}

export function FileDrop({ onFiles, multiple = true, directory = false, disabled }: Props) {
  const { t } = useI18n();
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setDragging(false);
      if (event.dataTransfer.files.length > 0) {
        onFiles(event.dataTransfer.files);
      }
    },
    [onFiles],
  );

  return (
    <div
      className={`file-drop${dragging ? " dragging" : ""}${disabled ? " disabled" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <CloudUpload size={36} strokeWidth={1.5} color="#64748b" />
      <p>{t("drop.hint")}</p>
      <div className="file-drop-actions">
        <label className="btn">
          {t("drop.files")}
          <input
            type="file"
            multiple={multiple}
            hidden
            disabled={disabled}
            onChange={(event) => {
              if (event.target.files) {
                onFiles(event.target.files);
              }
              event.target.value = "";
            }}
          />
        </label>
        {directory && (
          <label className="btn">
            {t("drop.directory")}
            <input
              type="file"
              multiple
              hidden
              // @ts-expect-error webkitdirectory is non-standard but widely supported
              webkitdirectory=""
              disabled={disabled}
              onChange={(event) => {
                if (event.target.files) {
                  onFiles(event.target.files);
                }
                event.target.value = "";
              }}
            />
          </label>
        )}
      </div>
    </div>
  );
}
