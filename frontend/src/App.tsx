import React, { useEffect } from 'react';
import { Layout, Menu } from 'antd';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { 
  FormatPainterOutlined, 
  FileTextOutlined, 
  CheckSquareOutlined, 
  DashboardOutlined 
} from '@ant-design/icons';
import axios from 'axios';

// Pages
import DesignPage from './pages/DesignPage';
import PrdPage from './pages/PrdPage';
import TestCasePage from './pages/TestCasePage';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';

const { Header, Content, Sider } = Layout;

// Layout component for protected routes
const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
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
            {children}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Interceptors are now handled in utils/request.ts
  }, []);

  // If we are on login page, just render it
  if (location.pathname === '/login') {
    return <Routes><Route path="/login" element={<LoginPage />} /></Routes>;
  }

  // Simple auth check
  const token = localStorage.getItem('token');
  if (!token) {
    // Redirect to login if not authenticated
    // We need to use useEffect to navigate to avoid rendering during state update warning
    // But returning null + navigate in useEffect is cleaner, 
    // or just render LoginPage directly if we want to block access immediately
    // For now let's just use a direct check
    return <LoginPage />;
  }

  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<DesignPage />} />
        <Route path="/design" element={<DesignPage />} />
        <Route path="/prd" element={<PrdPage />} />
        <Route path="/testcases" element={<TestCasePage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </MainLayout>
  );
};

export default App;
