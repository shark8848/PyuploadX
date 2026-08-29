import React from "react";
import ReactDOM from "react-dom/client";
import { message } from "antd";
import { App } from "./App";
import "./styles.css";

// 全局提示：右上角展示、6 秒后自动消失（进度条见 styles.css）。
message.config({ duration: 6, maxCount: 3, pauseOnHover: true, top: 24 });

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
