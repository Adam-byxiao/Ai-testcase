import type { Meta, StoryObj } from '@storybook/react';
import { PriorityTag } from './PriorityTag';

const meta = {
  title: 'Components/PriorityTag',
  component: PriorityTag,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof PriorityTag>;

export default meta;
type Story = StoryObj<typeof meta>;

export const High: Story = {
  args: {
    priority: 'High',
  },
};

export const Medium: Story = {
  args: {
    priority: 'Medium',
  },
};

export const Low: Story = {
  args: {
    priority: 'Low',
  },
};
