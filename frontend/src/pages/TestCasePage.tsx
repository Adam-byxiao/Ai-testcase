import React, { useState } from 'react';
import { Table, Button, Space, Typography, Tag, message } from 'antd';
import axios from 'axios';

const { Title, Text } = Typography;

const TestCasePage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any[]>([
    {
      id: 'TC-001',
      scenario: '正常使用手机号和正确验证码登录',
      preconditions: '用户已注册，且处于未登录状态',
      steps: '1. 输入手机号 2. 点击获取验证码 3. 输入收到的验证码 4. 点击登录',
      expected_result: '登录成功，跳转至首页',
      priority: 'High',
      script_bound: false
    }
  ]);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      // Mocking fetching PRD data from store
      const prdItems = [
        { id: 'PRD-001', title: '用户登录功能', description: '手机号验证码登录', priority: 'High', status: 'Draft', assignee: '张三' }
      ];
      const res = await axios.post('/api/testcases/generate', prdItems);
      setData(res.data.test_cases);
      message.success('测试用例生成成功');
    } catch (err) {
      message.error('生成失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { title: '用例 ID', dataIndex: 'id', key: 'id', width: 100 },
    { title: '测试场景', dataIndex: 'scenario', key: 'scenario' },
    { title: '前置条件', dataIndex: 'preconditions', key: 'preconditions' },
    { title: '操作步骤', dataIndex: 'steps', key: 'steps', ellipsis: true },
    { title: '预期结果', dataIndex: 'expected_result', key: 'expected_result' },
    { 
      title: '优先级', 
      dataIndex: 'priority', 
      key: 'priority',
      render: (p: string) => <Tag color={p === 'High' ? 'red' : 'blue'}>{p}</Tag>
    },
    { 
      title: '自动化脚本', 
      dataIndex: 'script_bound', 
      key: 'script_bound',
      render: (bound: boolean) => <Tag color={bound ? 'green' : 'default'}>{bound ? '已绑定' : '未绑定'}</Tag>
    },
    {
      title: '操作',
      key: 'action',
      render: () => (
        <Space size="middle">
          <a>编辑</a>
          <a>绑定脚本</a>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>用例阶段</Title>
          <Text type="secondary">根据需求条目自动推荐测试用例模板，输出可执行用例集</Text>
        </div>
        <Space>
          <Button type="primary" onClick={handleGenerate} loading={loading}>AI 自动生成用例</Button>
          <Button>导出测试集</Button>
        </Space>
      </div>

      <Table columns={columns} dataSource={data} rowKey="id" />
    </div>
  );
};

export default TestCasePage;
