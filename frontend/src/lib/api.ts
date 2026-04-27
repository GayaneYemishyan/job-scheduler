import type { DashboardData, User, TaskStatus } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000';
async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    credentials: 'include',
    headers: {
      ...options.headers,
    },
  });
  return res;
}

export async function getDashboard(): Promise<DashboardData> {
  const res = await fetchWithAuth('/dashboard-data');
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Authentication required. Please sign in.');
    }
    throw new Error('Failed to fetch dashboard');
  }
  return res.json();
}

export async function createTask(data: {
  name: string;
  department: string;
  priority: number;
  deadline: string;
  estimated_duration: number;
  dependencies: string[];
  description?: string;
  assigned_to?: string;
}): Promise<void> {
  const formData = new FormData();
  formData.append('name', data.name);
  formData.append('department', data.department);
  formData.append('priority', String(data.priority));
  formData.append('deadline', data.deadline);
  formData.append('estimated_duration', String(data.estimated_duration));
  if (data.description) formData.append('description', data.description);
  if (data.assigned_to) formData.append('assigned_to', data.assigned_to);
  data.dependencies.forEach(d => formData.append('dependencies', d));

  const res = await fetchWithAuth('/tasks/create', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to create task');
}

export async function startNextTask(): Promise<void> {
  const res = await fetchWithAuth('/tasks/start-next', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start next task');
}

export async function completeTask(taskId: string): Promise<void> {
  const res = await fetchWithAuth(`/tasks/${taskId}/complete`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to complete task');
}

export async function cancelTask(taskId: string): Promise<void> {
  const res = await fetchWithAuth(`/tasks/${taskId}/cancel`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to cancel task');
}

export async function rebalanceQueue(): Promise<void> {
  const res = await fetchWithAuth('/tasks/rebalance', { method: 'POST' });
  if (!res.ok) throw new Error('Failed to rebalance queue');
}

export async function updateTask(
  taskId: string,
  data: {
    name: string;
    department: string;
    priority: number;
    deadline: string;
    estimated_duration: number;
    status?: TaskStatus;
    description?: string;
    assigned_to?: string;
  }
): Promise<void> {
  const formData = new FormData();
  formData.append('name', data.name);
  formData.append('department', data.department);
  formData.append('priority', String(data.priority));
  formData.append('deadline', data.deadline);
  formData.append('estimated_duration', String(data.estimated_duration));
  if (data.status) formData.append('status', data.status);
  if (data.description) formData.append('description', data.description);
  if (data.assigned_to) formData.append('assigned_to', data.assigned_to);

  const res = await fetchWithAuth(`/tasks/${taskId}/edit`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to update task');
}

export async function signIn(email: string, password: string): Promise<User> {
  const formData = new FormData();
  formData.append('mode', 'signin');
  formData.append('email', email);
  formData.append('password', password);

  const res = await fetchWithAuth('/auth', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || 'Sign in failed');
  }
  const data = await res.json();
  return data.user || data;
}

export async function signUp(
  email: string,
  password: string,
  fullName: string
): Promise<User> {
  const formData = new FormData();
  formData.append('mode', 'signup');
  formData.append('email', email);
  formData.append('password', password);
  formData.append('full_name', fullName);
  const res = await fetchWithAuth('/auth', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || 'Sign up failed');
  }
  const data = await res.json();
  return data.user || data;
}

export async function logout(): Promise<void> {
  await fetchWithAuth('/logout');
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const res = await fetchWithAuth('/api/me');
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
