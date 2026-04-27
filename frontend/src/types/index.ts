export type TaskStatus = 'pending' | 'ready' | 'in_progress' | 'done' | 'delayed' | 'cancelled';

export type PriorityLevel = 1 | 2 | 3 | 4;

export interface Task {
  task_id: string;
  name: string;
  priority: number;
  base_priority: number;
  priority_level: PriorityLevel;
  deadline: string;
  department: string;
  assigned_to?: string;
  estimated_duration: number;
  dependencies: string[];
  description?: string;
  status: TaskStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  wait_time: number;
  delay?: number;
  heap_index?: number | null;
  effective_priority?: number;
}

export interface GraphNode {
  id: string;
  label: string;
  title: string;
  group: TaskStatus;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface DashboardData {
  user: {
    id: string;
    email: string;
    full_name: string;
  };
  tasks: Task[];
  history: Task[];
  queue: Task[];
  in_progress: Task[];
  running_task_id: string | null;
  stats: {
    completed: number;
    cancelled: number;
    total: number;
  };
  avg_delay: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  critical_path: string[];
  critical_duration: number;
  now: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
}
