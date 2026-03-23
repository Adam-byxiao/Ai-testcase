import React, { useState, useEffect } from 'react';
import { Table, Button, Space, Typography, Tag, message, Modal, Form, Input, Select, Switch } from 'antd';
import axios from '../utils/request';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

const TestCasePage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<any[]>([]);
  const [editingItem, setEditingItem] = useState<any | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm] = Form.useForm();
  const navigate = useNavigate();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/testcases');
      setData(res.data);
    } catch (err: any) {
      message.error('获取测试用例失败: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openEditModal = (record: any) => {
    setEditingItem(record);
    editForm.setFieldsValue({
      scenario: record.scenario,
      preconditions: record.preconditions,
      steps: record.steps,
      expected_result: record.expected_result,
      priority: record.priority,
      status: record.status,
      script_bound: record.script_bound,
    });
    setEditOpen(true);
  };

  const handleEditSave = async () => {
    try {
      const values = await editForm.validateFields();
      if (!editingItem) return;
      const res = await axios.put(`/api/testcases/${editingItem.id}`, values);
      const updated = res.data.testcase;
      setData((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      message.success('用例已更新');
      setEditOpen(false);
      setEditingItem(null);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('更新失败: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteTestCase = (record: any) => {
    Modal.confirm({
      title: '确认删除？',
      content: '该测试用例将被删除，且不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await axios.delete(`/api/testcases/${record.id}`);
          setData((prev) => prev.filter((item) => item.id !== record.id));
          message.success('用例已删除');
        } catch (err: any) {
          message.error('删除失败: ' + (err.response?.data?.detail || err.message));
        }
      }
    });
  };

  const columns = [
    { title: '用例 ID', dataIndex: 'id', key: 'id', width: 100 },
    { title: '关联需求ID', dataIndex: 'requirement_id', key: 'requirement_id', width: 120 },
    { title: '测试场景', dataIndex: 'scenario', key: 'scenario' },
    { title: '前置条件', dataIndex: 'preconditions', key: 'preconditions', ellipsis: true },
    { title: '操作步骤', dataIndex: 'steps', key: 'steps', ellipsis: true },
    { title: '预期结果', dataIndex: 'expected_result', key: 'expected_result', ellipsis: true },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      render: (p: string) => <Tag color={p === 'High' ? 'red' : p === 'Medium' ? 'orange' : 'blue'}>{p}</Tag>
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
      render: (_: any, record: any) => (
        <Space size="middle">
          <a onClick={() => openEditModal(record)}>编辑</a>
          <a onClick={() => handleDeleteTestCase(record)}>删除</a>
        </Space>
      ),
    },
  ];

  const handleClearTestCases = () => {
    Modal.confirm({
      title: '确认清空？',
      content: '这会删除所有测试用例，且不可恢复。',
      okText: '清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await axios.delete('/api/testcases/clear');
          setData([]);
          message.success('已清空全部测试用例。');
        } catch (err: any) {
          message.error('清空失败: ' + (err.response?.data?.detail || err.message));
        }
      }
    });
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>用例阶段</Title>
          <Text type="secondary">查看和管理已生成的测试用例</Text>
        </div>
        <Space>
          <Button onClick={fetchData} loading={loading}>刷新</Button>
          <Button danger onClick={handleClearTestCases}>清空</Button>
          <Button type="primary" onClick={() => navigate('/prd')}>去生成新用例</Button>
          <Button>导出测试集</Button>
        </Space>
      </div>

      <Table columns={columns} dataSource={data} rowKey="id" loading={loading} />

      <Modal
        title="编辑测试用例"
        open={editOpen}
        onOk={handleEditSave}
        onCancel={() => { setEditOpen(false); setEditingItem(null); }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="scenario" label="测试场景" rules={[{ required: true, message: '请输入测试场景' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="preconditions" label="前置条件">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="steps" label="操作步骤">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="expected_result" label="预期结果">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="priority" label="优先级" rules={[{ required: true, message: '请选择优先级' }]}
          >
            <Select options={[
              { label: 'High', value: 'High' },
              { label: 'Medium', value: 'Medium' },
              { label: 'Low', value: 'Low' },
            ]} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Input />
          </Form.Item>
          <Form.Item name="script_bound" label="自动化脚本" valuePropName="checked">
            <Switch checkedChildren="已绑定" unCheckedChildren="未绑定" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default TestCasePage;
