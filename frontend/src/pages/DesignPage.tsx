import React, { useState, useEffect, useRef } from 'react';
import { Upload, message, Card, Typography, Space, List, Input, Button, Divider, Tag } from 'antd';
import { InboxOutlined, SyncOutlined } from '@ant-design/icons';
import axios from '../utils/request';

const { Dragger } = Upload;
const { Title, Text } = Typography;

const DesignPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [prdItems, setPrdItems] = useState<any[]>([]);
  const [figmaInput, setFigmaInput] = useState('');
  const [figmaNodeId, setFigmaNodeId] = useState('');
  const [figmaStatus, setFigmaStatus] = useState<{
    fileKey: string;
    fileName?: string;
    nodeId?: string;
  } | null>(null);
  const [metrics, setMetrics] = useState<any | null>(null);
  const [figmaImageUrl, setFigmaImageUrl] = useState<string | null>(null);
  const [layerLinks, setLayerLinks] = useState<any[]>([]);
  const [layerArrowNodes, setLayerArrowNodes] = useState<any[]>([]);
  const [layerFlowchart, setLayerFlowchart] = useState<any | null>(null);
  const [flowBannerGroups, setFlowBannerGroups] = useState<any[]>([]);
  const [nodeMappings, setNodeMappings] = useState<any[]>([]);
  const [flowBannerFlowcharts, setFlowBannerFlowcharts] = useState<any[]>([]);
  const [compareData, setCompareData] = useState<{
    json_only: any[];
    merged: any[];
    added_by_vision: any[];
  } | null>(null);
  const [flowchartResult, setFlowchartResult] = useState<any | null>(null);
  const [flowchartImageUrl, setFlowchartImageUrl] = useState<string | null>(null);
  const [flowchartImageSize, setFlowchartImageSize] = useState<{ w: number; h: number } | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const overlayShapes = flowchartResult?.cv?.shapes || flowchartResult?.circles || [];
  const verifiedShapes = flowchartResult?.verified || [];

  const customRequest = async (options: any) => {
    const { file, onSuccess, onError } = options;
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post('/api/design/upload', formData);
      setPrdItems(res.data.items);
      setFigmaStatus(null);
      setMetrics(null);
      setFigmaImageUrl(null);
      setCompareData(null);
      setFlowchartResult(null);
      setLayerLinks([]);
      setLayerArrowNodes([]);
      setLayerFlowchart(null);
      setFlowBannerGroups([]);
      setNodeMappings([]);
      setFlowBannerFlowcharts([]);
      message.success('Parsed successfully and generated PRD items.');
      onSuccess(res.data);
    } catch (err: any) {
      message.error('Parse failed: ' + (err.response?.data?.detail || err.message));
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  const parseFigmaInput = (input: string) => {
    const trimmed = input.trim();
    if (!trimmed) return { fileKey: '', nodeId: '' };

    if (!/^https?:\/\//i.test(trimmed)) {
      return { fileKey: trimmed, nodeId: '' };
    }

    try {
      const url = new URL(trimmed);
      const parts = url.pathname.split('/').filter(Boolean);
      const fileIndex = parts.findIndex(p => p === 'file' || p === 'design');
      const fileKey = fileIndex >= 0 ? (parts[fileIndex + 1] || '') : '';
      let nodeId = url.searchParams.get('node-id') || '';
      if (nodeId && nodeId.indexOf(':') === -1 && nodeId.indexOf('-') !== -1) {
        nodeId = nodeId.replace('-', ':');
      }
      return { fileKey, nodeId };
    } catch {
      return { fileKey: '', nodeId: '' };
    }
  };

  const handleFigmaFetch = async () => {
    const parsed = parseFigmaInput(figmaInput);
    const fileKey = parsed.fileKey;
    const nodeId = figmaNodeId.trim() || parsed.nodeId;

    if (!fileKey) {
      message.error('Please provide a valid Figma URL or file key.');
      return;
    }

    setLoading(true);
    try {
      const res = await axios.post('/api/design/figma', {
        file_key: fileKey,
        node_id: nodeId || undefined,
      });
      setPrdItems(res.data.items);
      setMetrics(res.data.metrics || null);
      setFigmaImageUrl(res.data.figma?.image_url || null);
      setLayerLinks(res.data.layer_links || []);
      setLayerArrowNodes(res.data.layer_arrow_nodes || []);
      setLayerFlowchart(res.data.layer_flowchart || null);
      setFlowBannerGroups(res.data.flow_banner_groups || []);
      setNodeMappings(res.data.node_mappings || []);
      setFlowBannerFlowcharts(res.data.flow_banner_flowcharts || []);
      setCompareData(null);
      setFlowchartResult(null);
      setFigmaStatus({
        fileKey: res.data.figma?.file_key || fileKey,
        fileName: res.data.figma?.file_name,
        nodeId: res.data.figma?.node_id || nodeId || undefined,
      });
      message.success('Parsed successfully and generated PRD items.');
    } catch (err: any) {
      message.error('Parse failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleFigmaCompare = async () => {
    const parsed = parseFigmaInput(figmaInput);
    const fileKey = parsed.fileKey;
    const nodeId = figmaNodeId.trim() || parsed.nodeId;

    if (!fileKey) {
      message.error('Please provide a valid Figma URL or file key.');
      return;
    }

    setLoading(true);
    try {
      const res = await axios.post('/api/design/figma-compare', {
        file_key: fileKey,
        node_id: nodeId || undefined,
      });
      setCompareData({
        json_only: res.data.json_only || [],
        merged: res.data.merged || [],
        added_by_vision: res.data.added_by_vision || [],
      });
      setMetrics(res.data.metrics || null);
      setFigmaImageUrl(res.data.figma?.image_url || null);
      setLayerLinks(res.data.layer_links || []);
      setLayerArrowNodes(res.data.layer_arrow_nodes || []);
      setLayerFlowchart(res.data.layer_flowchart || null);
      setFlowBannerGroups(res.data.flow_banner_groups || []);
      setNodeMappings(res.data.node_mappings || []);
      setFlowBannerFlowcharts(res.data.flow_banner_flowcharts || []);
      setPrdItems([]);
      setFlowchartResult(null);
      setFigmaStatus({
        fileKey: res.data.figma?.file_key || fileKey,
        fileName: res.data.figma?.file_name,
        nodeId: res.data.figma?.node_id || nodeId || undefined,
      });
      message.success('Compare results generated.');
    } catch (err: any) {
      message.error('Compare failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleFlowchartUpload = async (options: any) => {
    const { file, onSuccess, onError } = options;
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      setFlowchartImageUrl(URL.createObjectURL(file));
      const res = await axios.post('/api/design/flowchart/circle-detect-upload', formData);
      setFlowchartResult(res.data);
      message.success('Flowchart parsed from image.');
      onSuccess(res.data);
    } catch (err: any) {
      message.error('Flowchart parse failed: ' + (err.response?.data?.detail || err.message));
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!canvasRef.current || !imgRef.current || overlayShapes.length === 0 || !flowchartImageSize) {
      return;
    }
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const displayWidth = imgRef.current.clientWidth;
    const displayHeight = imgRef.current.clientHeight;
    canvas.width = displayWidth;
    canvas.height = displayHeight;

    const scaleX = displayWidth / flowchartImageSize.w;
    const scaleY = displayHeight / flowchartImageSize.h;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const drawBox = (bbox: number[], stroke: string, fill: string, width: number) => {
      const [x, y, w, h] = bbox || [0, 0, 0, 0];
      const dx = x * scaleX;
      const dy = y * scaleY;
      const dw = w * scaleX;
      const dh = h * scaleY;
      ctx.lineWidth = width;
      ctx.strokeStyle = stroke;
      ctx.fillStyle = fill;
      ctx.strokeRect(dx, dy, dw, dh);
      ctx.fillRect(dx, dy, dw, dh);
    };

    overlayShapes.forEach((s: any) => {
      drawBox(s.bbox, '#ff4d4f', 'rgba(255,77,79,0.12)', 2);
    });

    verifiedShapes.forEach((s: any) => {
      drawBox(s.bbox, '#52c41a', 'rgba(82,196,26,0.12)', 3);
    });
  }, [overlayShapes, verifiedShapes, flowchartImageSize]);

  return (
    <div>
      <Title level={3}>Design Stage</Title>
      <Text type="secondary">
        Fetch from Figma online or upload a Figma JSON file to generate structured PRD items.
      </Text>

      <Card style={{ marginTop: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            value={figmaInput}
            onChange={(e) => setFigmaInput(e.target.value)}
            placeholder="Figma URL or file key"
          />
          <Input
            value={figmaNodeId}
            onChange={(e) => setFigmaNodeId(e.target.value)}
            placeholder="Optional node id (e.g. 123:456)"
          />
          <Button type="primary" onClick={handleFigmaFetch} loading={loading}>
            Fetch from Figma
          </Button>
          <Button onClick={handleFigmaCompare} loading={loading}>
            Compare (JSON vs Fusion)
          </Button>
        </Space>
      </Card>

      <Card style={{ marginTop: 24 }} title="通过图片上传识别流程图">
        <Upload.Dragger
          customRequest={handleFlowchartUpload}
          showUploadList={false}
          accept=".png,.jpg,.jpeg"
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽上传流程图截图</p>
          <p className="ant-upload-hint">支持 PNG/JPG</p>
        </Upload.Dragger>
      </Card>

      {figmaStatus && (
        <Card title="Figma Parse Status" style={{ marginTop: 24 }}>
          <List
            dataSource={[
              {
                label: 'File Name',
                value: figmaStatus.fileName || '(unknown)'
              },
              {
                label: 'File Key',
                value: figmaStatus.fileKey
              },
              {
                label: 'Node ID',
                value: figmaStatus.nodeId || '(none)'
              },
            ]}
            renderItem={item => (
              <List.Item>
                <Space>
                  <Text type="secondary">{item.label}:</Text>
                  <Text>{item.value}</Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>
      )}

      {layerLinks.length > 0 && (
        <Card title="Layer 连接关系（JSON 解析）" style={{ marginTop: 24 }}>
          <List
            dataSource={layerLinks}
            renderItem={(item: any) => (
              <List.Item>
                <Space>
                  <Text strong>{item.from_name || item.from_id}</Text>
                  <Text>→</Text>
                  <Text strong>{item.to_name || item.to_id || '(unknown)'}</Text>
                  {item.source && (
                    <Tag color={item.source === 'reaction' ? 'green' : 'blue'}>
                      {item.source}
                    </Tag>
                  )}
                </Space>
              </List.Item>
            )}
          />
        </Card>
      )}

      {layerArrowNodes.length > 0 && (
        <Card title="Layer 箭头节点（原始结构）" style={{ marginTop: 24 }}>
          <List
            dataSource={layerArrowNodes}
            renderItem={(item: any) => (
              <List.Item>
                <Space>
                  <Text strong>{item.name}</Text>
                  <Tag>{item.type || 'NODE'}</Tag>
                  {item.id && <Text type="secondary">{item.id}</Text>}
                </Space>
              </List.Item>
            )}
          />
        </Card>
      )}

      {layerFlowchart && (
        <Card title="流程图（基于 Layer 连接）" style={{ marginTop: 24 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <Text type="secondary">起点:</Text>
              <Text>{(layerFlowchart.starts || []).join(' / ') || '(none)'}</Text>
              {layerFlowchart.has_cycle && <Tag color="red">Cycle</Tag>}
            </Space>
            <Text type="secondary">Topological 顺序（近似主流程）</Text>
            <Text>{(layerFlowchart.topo || []).join(' → ') || '(none)'}</Text>
            <Divider />
            <Text type="secondary">Edges</Text>
            <List
              dataSource={layerFlowchart.edges || []}
              renderItem={(item: any) => (
                <List.Item>
                  <Space>
                    <Text strong>{item.from}</Text>
                    <Text>→</Text>
                    <Text strong>{item.to}</Text>
                    {item.source && <Tag>{item.source}</Tag>}
                  </Space>
                </List.Item>
              )}
            />
          </Space>
        </Card>
      )}

      {flowBannerGroups.length > 0 && (
        <Card title="Flow Banner 分组流程" style={{ marginTop: 24 }}>
          <List
            dataSource={flowBannerGroups}
            renderItem={(item: any) => (
              <List.Item>
                {(() => {
                  const labels = new Set(
                    (item.nodes || []).map((n: any) => n.label || n.meaning).filter(Boolean)
                  );
                  const norm = (s: string) =>
                    (s || '')
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, ' ')
                      .trim();
                  const labelArr = Array.from(labels).map((l: any) => String(l || ''));
                  const matchLabel = (name: string) => {
                    const n = norm(name);
                    return labelArr.find((l: string) => {
                      const ln = norm(l);
                      return ln && (ln.includes(n) || n.includes(ln));
                    });
                  };
                  const jsonEdges = (layerLinks || []).filter((e: any) => {
                    const fromMatch = matchLabel(e.from_name || '');
                    const toMatch = matchLabel(e.to_name || '');
                    return Boolean(fromMatch && toMatch);
                  });
                  const jsonNodes = Array.from(
                    new Set(
                      jsonEdges.flatMap((e: any) => [e.from_name, e.to_name]).filter(Boolean)
                    )
                  );
                  return (
                    <div style={{ width: '100%' }}>
                <List.Item.Meta
                  title={
                    <Space>
                      <strong>{item.feature_label || '(unknown)'}</strong>
                      {item.confidence != null && <Tag>conf: {Number(item.confidence).toFixed(2)}</Tag>}
                    </Space>
                  }
                  description={
                    <>
                      <Text type="secondary">Nodes: </Text>
                      <Text>
                        {(item.nodes || [])
                          .map((n: any) => n.label || n.meaning || '(unknown)')
                          .join(' / ') || '(none)'}
                      </Text>
                      <br />
                      <Text type="secondary">Edges: </Text>
                      <Text>
                        {(item.edges || [])
                          .map((e: any) => `${e.from} -> ${e.to}${e.trigger ? ` (${e.trigger})` : ''}`)
                          .join(' | ') ||
                          (item.raw_arrows || []).join(' | ') ||
                          '(none)'}
                      </Text>
                      <br />
                      <Text type="secondary">JSON Edges: </Text>
                      <Text>
                        {(jsonEdges || []).length > 0 ? (
                          <Space wrap>
                            {(jsonEdges || []).map((e: any, idx: number) => (
                              <Tag key={`${e.from_name}-${e.to_name}-${idx}`} color="cyan">
                                {e.from_name} → {e.to_name}
                              </Tag>
                            ))}
                          </Space>
                        ) : (
                          '(none)'
                        )}
                      </Text>
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary">JSON 边关系可视化: </Text>
                        {(jsonEdges || []).length > 0 ? (
                          <svg width="100%" height="80" viewBox="0 0 800 80" style={{ border: '1px solid #f0f0f0', borderRadius: 6 }}>
                            <defs>
                              <marker id="arrow" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
                                <path d="M0,0 L0,6 L9,3 z" fill="#13c2c2" />
                              </marker>
                            </defs>
                            {jsonNodes.map((n, i) => {
                              const x = 40 + i * (720 / Math.max(1, jsonNodes.length - 1));
                              return (
                                <g key={n}>
                                  <circle cx={x} cy={20} r={10} fill="#13c2c2" />
                                  <text x={x} y={45} textAnchor="middle" fontSize="10" fill="#555">{n}</text>
                                </g>
                              );
                            })}
                            {(jsonEdges || []).map((e: any, i: number) => {
                              const fromIdx = jsonNodes.indexOf(e.from_name);
                              const toIdx = jsonNodes.indexOf(e.to_name);
                              if (fromIdx === -1 || toIdx === -1) return null;
                              const x1 = 40 + fromIdx * (720 / Math.max(1, jsonNodes.length - 1));
                              const x2 = 40 + toIdx * (720 / Math.max(1, jsonNodes.length - 1));
                              return (
                                <line key={`${e.from_name}-${e.to_name}-${i}`} x1={x1} y1={20} x2={x2} y2={20} stroke="#13c2c2" strokeWidth="2" markerEnd="url(#arrow)" />
                              );
                            })}
                          </svg>
                        ) : (
                          <Text>(none)</Text>
                        )}
                      </div>
                    </>
                  }
                />
                    </div>
                  );
                })()}
              </List.Item>
            )}
          />
        </Card>
      )}

      {nodeMappings.length > 0 && (
        <Card title="视觉节点 ⇄ JSON 节点映射" style={{ marginTop: 24 }}>
          <List
            dataSource={nodeMappings}
            renderItem={(item: any) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <strong>{item.feature_label || '(unknown)'}</strong>
                      {item.source && <Tag color={item.source === 'llm' ? 'purple' : 'blue'}>{item.source}</Tag>}
                      {item.error && <Tag color="red">mapping_error</Tag>}
                    </Space>
                  }
                  description={
                    <Space wrap>
                      {(item.mappings || []).map((m: any, idx: number) => (
                        <Tag key={`${m.visual_label}-${idx}`} color={m.score >= 0.6 ? 'green' : 'orange'}>
                          {m.visual_label} → {m.json_name || '(none)'} ({m.score})
                        </Tag>
                      ))}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {flowBannerFlowcharts.length > 0 && (
        <Card title="Flow Banner 逻辑流程（视觉排序 + JSON 边）" style={{ marginTop: 24 }}>
          <List
            dataSource={flowBannerFlowcharts}
            renderItem={(item: any) => (
              <List.Item>
                <List.Item.Meta
                  title={<strong>{item.feature_label || '(unknown)'}</strong>}
                  description={
                    <>
                      <Text type="secondary">Ordered Nodes: </Text>
                      <Text>
                        {(item.flowchart?.ordered_nodes || [])
                          .map((n: any) => n.label || n.meaning || '(unknown)')
                          .join(' → ') || '(none)'}
                      </Text>
                      <br />
                      <Text type="secondary">Starts/Ends/Branches: </Text>
                      <Text>
                        Start: {(item.flowchart?.starts || []).join(' / ') || '(none)'} |
                        End: {(item.flowchart?.ends || []).join(' / ') || '(none)'} |
                        Branch: {(item.flowchart?.branches || []).join(' / ') || '(none)'}
                      </Text>
                      <br />
                      <Text type="secondary">Edges: </Text>
                      <Space wrap>
                        {(item.flowchart?.edges || []).map((e: any, idx: number) => (
                          <Tag key={`${e.from}-${e.to}-${idx}`} color={e.source === 'vision' ? 'purple' : e.source === 'json' ? 'blue' : 'gold'}>
                            {e.from} → {e.to} ({e.source})
                          </Tag>
                        ))}
                      </Space>
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary">流程图可视化: </Text>
                        <svg width="100%" height="120" viewBox="0 0 800 120" style={{ border: '1px solid #f0f0f0', borderRadius: 6 }}>
                          <defs>
                            <marker id="arrow2" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
                              <path d="M0,0 L0,6 L9,3 z" fill="#722ed1" />
                            </marker>
                          </defs>
                          {(item.flowchart?.ordered_nodes || []).map((n: any, i: number) => {
                            const x = 60 + i * (680 / Math.max(1, (item.flowchart?.ordered_nodes || []).length - 1));
                            return (
                              <g key={i}>
                                <circle cx={x} cy={40} r={12} fill="#722ed1" />
                                <text x={x} y={70} textAnchor="middle" fontSize="10" fill="#555">
                                  {n.label || n.meaning || 'node'}
                                </text>
                              </g>
                            );
                          })}
                          {(item.flowchart?.edges || []).map((e: any, i: number) => {
                            const labels = (item.flowchart?.ordered_nodes || []).map((n: any) => n.label || n.meaning);
                            const fromIdx = labels.indexOf(e.from);
                            const toIdx = labels.indexOf(e.to);
                            if (fromIdx === -1 || toIdx === -1) return null;
                            const x1 = 60 + fromIdx * (680 / Math.max(1, labels.length - 1));
                            const x2 = 60 + toIdx * (680 / Math.max(1, labels.length - 1));
                            return (
                              <line key={i} x1={x1} y1={40} x2={x2} y2={40} stroke="#722ed1" strokeWidth="2" markerEnd="url(#arrow2)" />
                            );
                          })}
                        </svg>
                      </div>
                    </>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      <Card style={{ marginTop: 24 }}>
        <Dragger
          customRequest={customRequest}
          showUploadList={false}
          accept=".json"
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">Click or drag file to this area</p>
          <p className="ant-upload-hint">Supports Figma JSON files</p>
        </Dragger>
      </Card>

      {loading && (
        <div style={{ textAlign: 'center', marginTop: 40 }}>
          <SyncOutlined spin style={{ fontSize: 32, color: '#1890ff' }} />
          <p style={{ marginTop: 16 }}>Parsing design, please wait...</p>
        </div>
      )}

      {figmaImageUrl && (
        <Card title="Figma 视觉预览" style={{ marginTop: 24 }}>
          <img
            src={figmaImageUrl}
            alt="Figma Visual Preview"
            style={{ width: '100%', borderRadius: 8, border: '1px solid #f0f0f0' }}
          />
        </Card>
      )}

      {metrics && (
        <Card title="识别评估" style={{ marginTop: 24 }}>
          <List
            dataSource={[
              { label: 'JSON 节点数', value: metrics.json_node_count },
              { label: '视觉组件数', value: metrics.visual_component_count },
              { label: '类型重叠比例', value: metrics.type_overlap_ratio },
            ]}
            renderItem={(item) => (
              <List.Item>
                <Space>
                  <Text type="secondary">{item.label}:</Text>
                  <Text>{String(item.value ?? '-')}</Text>
                </Space>
              </List.Item>
            )}
          />
          {metrics.visual_component_count <= 10 && (
            <Text type="warning">视觉组件数量偏低，可能需要调整截图范围或提高视觉识别提示。</Text>
          )}
          {metrics.type_overlap_ratio === 0 && (
            <Text type="warning" style={{ display: 'block', marginTop: 8 }}>
              结构与视觉类型无重叠，建议检查截图或提升层级识别精度。
            </Text>
          )}
        </Card>
      )}

      {compareData && (
        <Card title="融合对比（JSON vs 视觉融合）" style={{ marginTop: 24 }}>
          <Space align="start" size={32} style={{ width: '100%' }}>
            <div style={{ flex: 1 }}>
              <Text type="secondary">JSON Only</Text>
              <List
                dataSource={compareData.json_only}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      title={<strong>{item.title}</strong>}
                      description={item.description}
                    />
                  </List.Item>
                )}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Text type="secondary">Merged (Vision + JSON)</Text>
              <List
                dataSource={compareData.merged}
                renderItem={(item) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <Space>
                          <strong>{item.title}</strong>
                          {item.source && (
                            <Tag color={item.source === 'Vision' ? 'purple' : item.source === 'Both' ? 'green' : 'blue'}>
                              {item.source}
                            </Tag>
                          )}
                        </Space>
                      }
                      description={item.description}
                    />
                  </List.Item>
                )}
              />
            </div>
          </Space>
          <Divider />
          <Text type="secondary">Added By Vision</Text>
          <List
            dataSource={compareData.added_by_vision}
            renderItem={(item) => (
              <List.Item>
                <List.Item.Meta
                  title={<strong>{item.title}</strong>}
                  description={item.description}
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {flowchartResult && (
        <Card title="流程图识别结果" style={{ marginTop: 24 }}>
          {flowchartImageUrl && (
            <div style={{ position: 'relative', width: '100%', marginBottom: 16 }}>
              <img
                ref={imgRef}
                src={flowchartImageUrl}
                alt="Flowchart Upload"
                style={{ width: '100%', borderRadius: 8, border: '1px solid #f0f0f0' }}
                onLoad={(e) => {
                  const img = e.currentTarget;
                  setFlowchartImageSize({ w: img.naturalWidth, h: img.naturalHeight });
                }}
              />
              <canvas
                ref={canvasRef}
                style={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none' }}
              />
            </div>
          )}
          <Text type="secondary">OpenCV 识别结果</Text>
          <List
            dataSource={overlayShapes}
            renderItem={(item: any) => (
              <List.Item>
                <Space>
                  <Text>{item.shape ? `shape: ${item.shape}` : 'circle'}</Text>
                  {item.radius != null && <Text type="secondary">r: {item.radius}</Text>}
                  <Text type="secondary">bbox: {JSON.stringify(item.bbox)}</Text>
                </Space>
              </List.Item>
            )}
          />
          <Divider />
          <Text type="secondary">圆屏节点（LLM 校验）</Text>
          <List
            dataSource={verifiedShapes}
            renderItem={(item: any) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <strong>{item.label || 'Screen'}</strong>
                      <Tag>{item.is_screen ? 'Screen' : 'Unknown'}</Tag>
                    </Space>
                  }
                  description={(item.components || []).join(' / ')}
                />
                <Text type="secondary">bbox: {JSON.stringify(item.bbox)}</Text>
              </List.Item>
            )}
          />
          {flowchartResult.semantic?.nodes && (
            <>
              <Divider />
              <Text type="secondary">多模态语义识别</Text>
              <List
                dataSource={flowchartResult.semantic?.nodes || []}
                renderItem={(item: any) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <Space>
                          <strong>{item.label}</strong>
                          <Tag>{item.shape || 'node'}</Tag>
                        </Space>
                      }
                      description={(item.components || []).join(' / ')}
                    />
                  </List.Item>
                )}
              />
            </>
          )}
          {flowchartResult.semantic?.edges && (
            <>
              <Divider />
              <Text type="secondary">边关系</Text>
              <List
                dataSource={flowchartResult.semantic?.edges || []}
                renderItem={(item: any) => (
                  <List.Item>
                    <Text>
                      {item.from} → {item.to} {item.label ? `(${item.label})` : ''}
                    </Text>
                  </List.Item>
                )}
              />
            </>
          )}
        </Card>
      )}

      {prdItems.length > 0 && (
        <Card title="Parsed Results: PRD Items" style={{ marginTop: 24 }}>
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
                    <Text type="secondary">Priority: {item.priority}</Text>
                    <Text type="secondary">Status: {item.status}</Text>
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
