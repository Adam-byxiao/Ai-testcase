import React from 'react';
import { Layout, Menu } from 'antd';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { 
  FormatPainterOutlined, 
  FileTextOutlined, 
  CheckSquareOutlined, 
  DashboardOutlined 
} from '@ant-design/icons';

// Pages
import DesignPage from './pages/DesignPage';
import PrdPage from './pages/PrdPage';
import TestCasePage from './pages/TestCasePage';
import DashboardPage from './pages/DashboardPage';

const { Header, Content, Sider } = Layout;

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/design', icon: <FormatPainterOutlined />, label: '设计阶段' },
    { key: '/prd', icon: <FileTextOutlined />, label: '需求阶段' },
    { key: '/testcases', icon: <CheckSquareOutlined />, label: '用例阶段' },
    { key: '/dashboard', icon: <DashboardOutlined />, label: '结果面板' },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', background: '#001529' }}>
        <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
          AI Testcase Platform
        </div>
      </Header>
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>
        <Layout style={{ padding: '24px 24px 24px' }}>
          <Content
            style={{
              padding: 24,
              margin: 0,
              minHeight: 280,
              background: '#fff',
              borderRadius: '8px'
            }}
          >
            <Routes>
              <Route path="/" element={<DesignPage />} />
              <Route path="/design" element={<DesignPage />} />
              <Route path="/prd" element={<PrdPage />} />
              <Route path="/testcases" element={<TestCasePage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default App;
