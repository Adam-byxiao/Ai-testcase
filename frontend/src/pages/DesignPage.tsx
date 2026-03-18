import React, { useState } from 'react';
import { Upload, message, Card, Typography, Space, List } from 'antd';
import { InboxOutlined, SyncOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Dragger } = Upload;
const { Title, Text } = Typography;

const DesignPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [prdItems, setPrdItems] = useState<any[]>([]);

  const customRequest = async (options: any) => {
    const { file, onSuccess, onError } = options;
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post('/api/design/upload', formData);
      setPrdItems(res.data.items);
      message.success('解析成功，已生成需求条目');
      onSuccess(res.data);
    } catch (err: any) {
      message.error('解析失败: ' + err.message);
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Title level={3}>设计阶段</Title>
      <Text type="secondary">上传 Figma JSON 或原型图，自动生成结构化需求条目</Text>
      
      <Card style={{ marginTop: 24 }}>
        <Dragger 
          customRequest={customRequest}
          showUploadList={false}
          accept=".json"
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">支持 Figma JSON 文件</p>
        </Dragger>
      </Card>

      {loading && (
        <div style={{ textAlign: 'center', marginTop: 40 }}>
          <SyncOutlined spin style={{ fontSize: 32, color: '#1890ff' }} />
          <p style={{ marginTop: 16 }}>AI 正在解析设计稿，请稍候...</p>
        </div>
      )}

      {prdItems.length > 0 && (
        <Card title="解析结果：结构化需求条目" style={{ marginTop: 24 }}>
          <List
            dataSource={prdItems}
            renderItem={item => (
              <List.Item>
                <List.Item.Meta
                  title={<Space><strong>{item.id}</strong> {item.title}</Space>}
                  description={item.description}
                />
                <div>
                  <Space>
                    <Text type="secondary">优先级: {item.priority}</Text>
                    <Text type="secondary">状态: {item.status}</Text>
                  </Space>
                </div>
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  );
};

export default DesignPage;
