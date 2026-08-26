import { useCallback, useState } from "react";

interface Props {
  onFiles: (files: FileList) => void;
  multiple?: boolean;
  directory?: boolean;
  disabled?: boolean;
}

export function FileDrop({ onFiles, multiple = true, directory = false, disabled }: Props) {
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
      <p>拖放文件到此处，或点击选择</p>
      <div className="file-drop-actions">
        <label className="btn">
          选择文件
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
            选择目录
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
