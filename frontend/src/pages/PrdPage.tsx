﻿import React, { useState, useEffect } from 'react';
import { Table, Button, Space, Typography, Tag, message, Modal, Form, Input, Select } from 'antd';
import axios from '../utils/request';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

const PrdPage: React.FC = () => {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [generating, setGenerating] = useState(false);
  const [editingItem, setEditingItem] = useState<any | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm] = Form.useForm();

  const navigate = useNavigate();

  useEffect(() => {
    fetchRequirements();
  }, []);

  const fetchRequirements = async () => {
    setLoading(true);
    try {
      const res = await axios.get('/api/requirements');
      setData(res.data);
    } catch (err: any) {
      message.error('获取需求列表失败');
    } finally {
      setLoading(false);
    }
  };

  const openEditModal = (record: any) => {
    setEditingItem(record);
    editForm.setFieldsValue({
      title: record.title,
      description: record.description,
      priority: record.priority,
      status: record.status,
      assignee: record.assignee,
    });
    setEditOpen(true);
  };

  const handleEditSave = async () => {
    try {
      const values = await editForm.validateFields();
      if (!editingItem) return;
      const res = await axios.put(`/api/requirements/${editingItem.id}`, values);
      const updated = res.data.requirement;
      setData((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      message.success('需求已更新');
      setEditOpen(false);
      setEditingItem(null);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('更新失败: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleDeleteRequirement = (record: any) => {
    Modal.confirm({
      title: '确认删除？',
      content: '该需求及关联用例将被删除，且不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await axios.delete(`/api/requirements/${record.id}`);
          setData((prev) => prev.filter((item) => item.id !== record.id));
          setSelectedRowKeys((prev) => prev.filter((id) => id !== record.id));
          message.success('需求已删除');
        } catch (err: any) {
          message.error('删除失败: ' + (err.response?.data?.detail || err.message));
        }
      }
    });
  };

  const columns = [
    { title: '需求ID', dataIndex: 'id', key: 'id' },
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
      render: (_: any, record: any) => (
        <Space size="middle">
          <a onClick={() => openEditModal(record)}>编辑</a>
          <a onClick={() => handleDeleteRequirement(record)}>删除</a>
        </Space>
      ),
    },
  ];

  const handleGenerateMD = async () => {
    if (data.length === 0) {
      message.warning('暂无需求数据');
      return;
    }
    try {
      const targetIds = selectedRowKeys.length > 0
        ? selectedRowKeys
        : data.map((item: any) => item.id);

      const res = await axios.post('/api/prd/generate-markdown', targetIds);
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

  const handleGenerateTestCases = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请至少选择一个需求项来生成测试用例');
      return;
    }

    setGenerating(true);
    try {
      const res = await axios.post('/api/testcases/generate', selectedRowKeys);
      Modal.success({
        title: '测试用例生成成功',
        content: `成功生成 ${res.data.test_cases.length} 条测试用例，点击确定前往用例页面查看。`,
        onOk: () => {
          navigate('/testcases');
        }
      });
    } catch (err: any) {
      message.error('生成失败: ' + (err.response?.data?.detail || err.message));
    } finally {
      setGenerating(false);
    }
  };

  const handleClearRequirements = () => {
    Modal.confirm({
      title: '确认清空？',
      content: '这会删除所有需求与关联用例，且不可恢复。',
      okText: '清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await axios.delete('/api/requirements/clear');
          setData([]);
          setSelectedRowKeys([]);
          message.success('已清空全部需求。');
        } catch (err: any) {
          message.error('清空失败: ' + (err.response?.data?.detail || err.message));
        }
      }
    });
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys);
    },
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>需求阶段</Title>
          <Text type="secondary">维护需求条目，并一键生成标准化需求文档</Text>
        </div>
        <Space>
          <Button onClick={fetchRequirements}>刷新</Button>
          <Button danger onClick={handleClearRequirements}>清空</Button>
          <Button type="default" onClick={handleGenerateMD}>导出文档 (MD)</Button>
          <Button
            type="primary"
            onClick={handleGenerateTestCases}
            loading={generating}
            disabled={selectedRowKeys.length === 0}
          >
            AI 生成测试用例 ({selectedRowKeys.length})
          </Button>
        </Space>
      </div>

      <Table
        rowSelection={rowSelection}
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
      />

      <Modal
        title="编辑需求"
        open={editOpen}
        onOk={handleEditSave}
        onCancel={() => { setEditOpen(false); setEditingItem(null); }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="priority" label="优先级" rules={[{ required: true, message: '请选择优先级' }]}>
            <Select options={[
              { label: 'High', value: 'High' },
              { label: 'Medium', value: 'Medium' },
              { label: 'Low', value: 'Low' },
            ]} />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Input />
          </Form.Item>
          <Form.Item name="assignee" label="负责人">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PrdPage;
