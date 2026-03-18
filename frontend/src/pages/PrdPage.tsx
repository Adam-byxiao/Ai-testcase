import React, { useState } from 'react';
import { Table, Button, Space, Typography, Tag, message } from 'antd';
import axios from 'axios';

const { Title, Text } = Typography;

const PrdPage: React.FC = () => {
  // Mock data for now, ideally managed by a global store (Zustand)
  const [data] = useState([
    {
      id: 'PRD-001',
      title: '用户登录功能',
      description: '用户可以通过手机号和验证码进行登录',
      priority: 'High',
      status: 'Draft',
      assignee: '张三'
    },
    {
      id: 'PRD-002',
      title: '个人中心展示',
      description: '展示用户头像、昵称及基本设置入口',
      priority: 'Medium',
      status: 'Review',
      assignee: '李四'
    }
  ]);

  const columns = [
    { title: '需求 ID', dataIndex: 'id', key: 'id' },
    { title: '标题', dataIndex: 'title', key: 'title' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { 
      title: '优先级', 
      dataIndex: 'priority', 
      key: 'priority',
      render: (p: string) => {
        const color = p === 'High' ? 'red' : p === 'Medium' ? 'orange' : 'green';
        return <Tag color={color}>{p}</Tag>;
      }
    },
    { title: '状态', dataIndex: 'status', key: 'status' },
    { title: '负责人', dataIndex: 'assignee', key: 'assignee' },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="middle">
          <a>编辑</a>
          <a>删除</a>
        </Space>
      ),
    },
  ];

  const handleGenerateMD = async () => {
    try {
      const res = await axios.post('/api/prd/generate-markdown', data);
      const blob = new Blob([res.data.markdown], { type: 'text/markdown' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'PRD_Document.md';
      a.click();
      message.success('需求文档导出成功');
    } catch (err) {
      message.error('导出失败');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>需求阶段</Title>
          <Text type="secondary">维护需求条目，并一键生成标准化需求文档</Text>
        </div>
        <Space>
          <Button type="primary" onClick={handleGenerateMD}>一键生成文档 (Markdown)</Button>
          <Button>新增需求</Button>
        </Space>
      </div>

      <Table columns={columns} dataSource={data} rowKey="id" />
    </div>
  );
};

export default PrdPage;
