import React, { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Typography } from 'antd';
import axios from 'axios';

const { Title, Text } = Typography;

const DashboardPage: React.FC = () => {
  const [metrics, setMetrics] = useState<any>({});

  useEffect(() => {
    // Fetch proxy metrics from backend as an example
    axios.get('/metrics').then(res => {
      setMetrics(res.data);
    }).catch(console.error);
  }, []);

  return (
    <div>
      <Title level={3}>结果可视化面板</Title>
      <Text type="secondary">实时展示需求→用例的覆盖率、执行通过率、缺陷分布等</Text>
      
      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="需求覆盖率" value={85} suffix="%" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="用例执行通过率" value={92} suffix="%" valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="遗留缺陷数" value={14} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="自动化脚本覆盖" value={45} suffix="%" />
          </Card>
        </Col>
      </Row>

      {/* System Metrics (Redundant Proxy) */}
      <Title level={4} style={{ marginTop: 40 }}>系统监控 (冗余代理机制)</Title>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic title="总 API 请求次数" value={metrics.total_requests || 0} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="代理直连切换次数" value={metrics.switch_count || 0} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="代理成功/失败" value={`${metrics.proxy_success || 0} / ${metrics.proxy_failures || 0}`} />
          </Card>
        </Col>
      </Row>
      
      <Card style={{ marginTop: 24, height: 300, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Text type="secondary">图表组件占位区 (可接入 ECharts 或 Ant Design Charts)</Text>
      </Card>
    </div>
  );
};

export default DashboardPage;
