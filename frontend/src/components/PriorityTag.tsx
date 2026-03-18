import React from 'react';
import { Tag } from 'antd';

export const PriorityTag: React.FC<{ priority: 'High' | 'Medium' | 'Low' }> = ({ priority }) => {
  const color = priority === 'High' ? 'red' : priority === 'Medium' ? 'orange' : 'green';
  return <Tag color={color}>{priority}</Tag>;
};
