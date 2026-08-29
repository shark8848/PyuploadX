import { useState } from "react";
import { Button, Card, Input, Space, Typography, message } from "antd";
import { KeyOutlined, LockOutlined } from "@ant-design/icons";
import * as api from "../api/client";

const { Title, Paragraph } = Typography;

interface LoginPageProps {
  onSuccess: () => void;
}

export default function LoginPage({ onSuccess }: LoginPageProps) {
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  const handleLogin = async () => {
    if (!token.trim()) {
      messageApi.warning("请输入 API Key");
      return;
    }
    setLoading(true);
    try {
      await api.verifyApiKey(token.trim());
      api.setApiToken(token.trim());
      localStorage.setItem("portal-token", token.trim());
      messageApi.success("登录成功");
      onSuccess();
    } catch {
      messageApi.error("API Key 无效，请检查后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      }}
    >
      {contextHolder}
      <Card
        style={{ width: 400, borderRadius: 12, boxShadow: "0 8px 32px rgba(0,0,0,0.15)" }}
        bordered={false}
      >
        <Space direction="vertical" size="large" style={{ width: "100%", textAlign: "center" }}>
          <div>
            <LockOutlined style={{ fontSize: 40, color: "#667eea" }} />
            <Title level={3} style={{ marginTop: 12, marginBottom: 4 }}>
              PyUploadX
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              文件上传与共享服务
            </Paragraph>
          </div>

          <Input.Password
            size="large"
            prefix={<KeyOutlined />}
            placeholder="请输入 API Key"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            onPressEnter={handleLogin}
            autoFocus
          />

          <Button type="primary" size="large" block loading={loading} onClick={handleLogin}>
            登录
          </Button>
        </Space>
      </Card>
    </div>
  );
}
