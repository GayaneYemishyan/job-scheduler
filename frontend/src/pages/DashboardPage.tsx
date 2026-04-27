import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import {
  getDashboard,
  createTask,
  startNextTask,
  completeTask,
  cancelTask,
  rebalanceQueue,
  updateTask,
} from '@/lib/api';
import type { DashboardData, Task, TaskStatus } from '@/types';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import {
  Network,
  Search,
  LogOut,
  Play,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Plus,
  List,
  History,
  BarChart3,
  AlertTriangle,
  TrendingUp,
  Zap,
  X,
  Filter,
  GitBranch,
  Edit,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const STATUS_COLORS: Record<TaskStatus, string> = {
  pending: '#4a4a5e',
  ready: '#7c6bff',
  in_progress: '#00d4ff',
  done: '#00e5a0',
  delayed: '#ff5a5a',
  cancelled: '#6b6b80',
};

const STATUS_BG: Record<TaskStatus, string> = {
  pending: 'bg-[#4a4a5e20] text-[#4a4a5e]',
  ready: 'bg-[#7c6bff20] text-[#7c6bff]',
  in_progress: 'bg-[#00d4ff20] text-[#00d4ff]',
  done: 'bg-[#00e5a020] text-[#00e5a0]',
  delayed: 'bg-[#ff5a5a20] text-[#ff5a5a]',
  cancelled: 'bg-[#6b6b8020] text-[#6b6b80]',
};

const PRIORITY_COLORS: Record<number, string> = {
  1: '#7c6bff',
  2: '#ffb347',
  3: '#ff6b6b',
  4: '#ff5a5a',
};

const DEPARTMENTS = ['Engineering', 'Design', 'Marketing', 'Operations', 'HR', 'Other'];

/* ------------------------------------------------------------------ */
/*  Graph Visualization (Canvas)                                       */
/* ------------------------------------------------------------------ */

interface GraphSimNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  radius: number;
  label: string;
  status: TaskStatus;
  priority: number;
}

interface GraphSimEdge {
  from: string;
  to: string;
  isCritical: boolean;
}

function GraphCanvas({
  data,
  selectedNode,
  onSelectNode,
  statusFilter,
}: {
  data: DashboardData;
  selectedNode: string | null;
  onSelectNode: (id: string | null) => void;
  statusFilter: TaskStatus | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<GraphSimNode[]>([]);
  const edgesRef = useRef<GraphSimEdge[]>([]);
  const cameraRef = useRef({ x: 0, y: 0, zoom: 1, targetX: 0, targetY: 0, targetZoom: 1 });
  const draggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const mouseRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const nodes: GraphSimNode[] = data.nodes.map((n) => {
      const task = data.tasks.find((t) => t.task_id === n.id);
      return {
        id: n.id,
        x: (Math.random() - 0.5) * 600,
        y: (Math.random() - 0.5) * 400,
        vx: 0,
        vy: 0,
        color: STATUS_COLORS[(n.group as TaskStatus) || 'pending'],
        radius: 8 + (task?.priority || 2) * 2,
        label: n.label.split('\\n')[1] || n.label,
        status: (n.group as TaskStatus) || 'pending',
        priority: task?.priority || 2,
      };
    });

    const edges: GraphSimEdge[] = data.edges.map((e) => ({
      from: e.from,
      to: e.to,
      isCritical: data.critical_path.includes(e.from) && data.critical_path.includes(e.to),
    }));

    nodesRef.current = nodes;
    edgesRef.current = edges;

    // Center camera
    cameraRef.current.x = 0;
    cameraRef.current.y = 0;
  }, [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = canvas.offsetWidth;
    let h = canvas.offsetHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    let animId: number;

    function animate() {
      ctx!.clearRect(0, 0, w, h);
      const cam = cameraRef.current;

      // Smooth camera
      cam.x += (cam.targetX - cam.x) * 0.1;
      cam.y += (cam.targetY - cam.y) * 0.1;
      cam.zoom += (cam.targetZoom - cam.zoom) * 0.1;

      const cx = w / 2 - cam.x * cam.zoom;
      const cy = h / 2 - cam.y * cam.zoom;

      // Physics
      nodesRef.current.forEach((node) => {
        // Center gravity
        node.vx += -node.x * 0.0005;
        node.vy += -node.y * 0.0005;

        // Repulsion
        nodesRef.current.forEach((other) => {
          if (node.id === other.id) return;
          const dx = node.x - other.x;
          const dy = node.y - other.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          if (dist < 200) {
            const force = 800 / (dist * dist);
            node.vx += (dx / dist) * force;
            node.vy += (dy / dist) * force;
          }
        });

        // Edge springs
        edgesRef.current.forEach((edge) => {
          if (edge.from === node.id) {
            const other = nodesRef.current.find((n) => n.id === edge.to);
            if (other) {
              const dx = other.x - node.x;
              const dy = other.y - node.y;
              const dist = Math.sqrt(dx * dx + dy * dy) || 1;
              const force = (dist - 150) * 0.0005;
              node.vx += (dx / dist) * force;
              node.vy += (dy / dist) * force;
            }
          }
        });

        node.vx *= 0.88;
        node.vy *= 0.88;
        node.x += node.vx;
        node.y += node.vy;
      });

      // Draw edges
      edgesRef.current.forEach((edge) => {
        const from = nodesRef.current.find((n) => n.id === edge.from);
        const to = nodesRef.current.find((n) => n.id === edge.to);
        if (!from || !to) return;

        const sx = cx + from.x * cam.zoom;
        const sy = cy + from.y * cam.zoom;
        const ex = cx + to.x * cam.zoom;
        const ey = cy + to.y * cam.zoom;

        ctx!.beginPath();
        ctx!.moveTo(sx, sy);
        ctx!.lineTo(ex, ey);

        if (edge.isCritical) {
          ctx!.strokeStyle = '#ff5a5a';
          ctx!.lineWidth = 2 * cam.zoom;
          ctx!.shadowColor = '#ff5a5a';
          ctx!.shadowBlur = 6;
        } else if (selectedNode && (edge.from === selectedNode || edge.to === selectedNode)) {
          ctx!.strokeStyle = '#7c6bff';
          ctx!.lineWidth = 2 * cam.zoom;
          ctx!.shadowColor = '#7c6bff';
          ctx!.shadowBlur = 4;
        } else {
          ctx!.strokeStyle = 'rgba(58, 58, 78, 0.5)';
          ctx!.lineWidth = Math.max(0.5, cam.zoom);
          ctx!.shadowBlur = 0;
        }
        ctx!.stroke();
        ctx!.shadowBlur = 0;
      });

      // Draw nodes
      nodesRef.current.forEach((node) => {
        if (statusFilter && node.status !== statusFilter) {
          // Dimmed
          const px = cx + node.x * cam.zoom;
          const py = cy + node.y * cam.zoom;
          ctx!.beginPath();
          ctx!.arc(px, py, node.radius * cam.zoom * 0.6, 0, Math.PI * 2);
          ctx!.fillStyle = node.color + '20';
          ctx!.fill();
          return;
        }

        const isSelected = selectedNode === node.id;
        const scale = isSelected ? 1.4 : 1;
        const px = cx + node.x * cam.zoom;
        const py = cy + node.y * cam.zoom;
        const r = node.radius * cam.zoom * scale;

        // Glow for active states
        if (node.status === 'ready' || node.status === 'in_progress' || node.status === 'delayed') {
          ctx!.beginPath();
          ctx!.arc(px, py, r * 2.5, 0, Math.PI * 2);
          ctx!.fillStyle = node.color + '12';
          ctx!.fill();
        }

        // Node
        ctx!.beginPath();
        ctx!.arc(px, py, r, 0, Math.PI * 2);
        ctx!.fillStyle = node.color;
        ctx!.fill();

        // Border - stronger for important statuses
        if (node.status === 'in_progress') {
          ctx!.strokeStyle = node.color;
          ctx!.lineWidth = isSelected ? 3 : 2;
          ctx!.stroke();
          // Double border for in progress
          ctx!.beginPath();
          ctx!.arc(px, py, r * 1.15, 0, Math.PI * 2);
          ctx!.strokeStyle = node.color + '40';
          ctx!.lineWidth = 1;
          ctx!.stroke();
        } else {
          ctx!.strokeStyle = isSelected ? '#ffffff' : node.color + '80';
          ctx!.lineWidth = isSelected ? 2.5 : 1;
          ctx!.stroke();
        }

        // Label
        if (isSelected || node.status === 'ready' || node.status === 'in_progress' || node.status === 'delayed') {
          ctx!.font = `${isSelected ? '600' : '500'} ${Math.max(10, 12 * cam.zoom)}px Inter, sans-serif`;
          ctx!.fillStyle = '#ffffff';
          ctx!.textAlign = 'center';
          ctx!.textBaseline = 'bottom';
          ctx!.shadowColor = '#0a0a0f';
          ctx!.shadowBlur = 4;
          ctx!.fillText(node.label, px, py - r - 4);
          ctx!.shadowBlur = 0;
        }

        // Status badge - small indicator at bottom right
        const statusIndicators: Record<TaskStatus, string> = {
          pending: 'P',
          ready: 'R',
          in_progress: '◉',
          done: '✓',
          delayed: '!',
          cancelled: '✕',
        };
        const badgeR = 5 * cam.zoom;
        ctx!.beginPath();
        ctx!.arc(px + r * 0.7, py + r * 0.7, badgeR, 0, Math.PI * 2);
        ctx!.fillStyle = node.color;
        ctx!.fill();
        ctx!.strokeStyle = '#0a0a0f';
        ctx!.lineWidth = 1;
        ctx!.stroke();
        ctx!.font = `600 ${Math.max(7, 8 * cam.zoom)}px Inter`;
        ctx!.fillStyle = '#ffffff';
        ctx!.textAlign = 'center';
        ctx!.textBaseline = 'middle';
        ctx!.fillText(statusIndicators[node.status], px + r * 0.7, py + r * 0.7);

        // Priority badge
        if (isSelected) {
          const priBadgeR = 8 * cam.zoom;
          ctx!.beginPath();
          ctx!.arc(px + r * 0.7, py - r * 0.7, priBadgeR, 0, Math.PI * 2);
          ctx!.fillStyle = PRIORITY_COLORS[node.priority] || '#7c6bff';
          ctx!.fill();
          ctx!.strokeStyle = '#0a0a0f';
          ctx!.lineWidth = 1.5;
          ctx!.stroke();
          ctx!.font = `600 ${Math.max(8, 9 * cam.zoom)}px Inter`;
          ctx!.fillStyle = '#ffffff';
          ctx!.textAlign = 'center';
          ctx!.textBaseline = 'middle';
          ctx!.fillText(String(node.priority), px + r * 0.7, py - r * 0.7);
        }
      });

      animId = requestAnimationFrame(animate);
    }

    animate();

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };

      if (draggingRef.current) {
        const dx = (e.clientX - dragStartRef.current.x) / cameraRef.current.zoom;
        const dy = (e.clientY - dragStartRef.current.y) / cameraRef.current.zoom;
        cameraRef.current.targetX -= dx;
        cameraRef.current.targetY -= dy;
        dragStartRef.current = { x: e.clientX, y: e.clientY };
      } else {
        // Hover check
        const cam = cameraRef.current;
        const cx = w / 2 - cam.x * cam.zoom;
        const cy = h / 2 - cam.y * cam.zoom;

        let hovered: string | null = null;
        for (const node of nodesRef.current) {
          const px = cx + node.x * cam.zoom;
          const py = cy + node.y * cam.zoom;
          const dx = mouseRef.current.x - px;
          const dy = mouseRef.current.y - py;
          if (Math.sqrt(dx * dx + dy * dy) < node.radius * cam.zoom + 5) {
            hovered = node.id;
            break;
          }
        }
        canvas.style.cursor = hovered ? 'pointer' : draggingRef.current ? 'grabbing' : 'grab';
      }
    };

    const handleMouseDown = (e: MouseEvent) => {
      draggingRef.current = true;
      dragStartRef.current = { x: e.clientX, y: e.clientY };

      // Check for click on node
      const cam = cameraRef.current;
      const cx = w / 2 - cam.x * cam.zoom;
      const cy = h / 2 - cam.y * cam.zoom;

      for (const node of nodesRef.current) {
        const px = cx + node.x * cam.zoom;
        const py = cy + node.y * cam.zoom;
        const dx = mouseRef.current.x - px;
        const dy = mouseRef.current.y - py;
        if (Math.sqrt(dx * dx + dy * dy) < node.radius * cam.zoom + 10) {
          onSelectNode(node.id);
          // Pan to node
          cameraRef.current.targetX = node.x;
          cameraRef.current.targetY = node.y;
          draggingRef.current = false;
          return;
        }
      }

      onSelectNode(null);
    };

    const handleMouseUp = () => {
      draggingRef.current = false;
    };

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
      cameraRef.current.targetZoom = Math.max(0.3, Math.min(5, cameraRef.current.targetZoom * zoomFactor));
    };

    const handleResize = () => {
      w = canvas.offsetWidth;
      h = canvas.offsetHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    };

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseUp);
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('mouseleave', handleMouseUp);
      canvas.removeEventListener('wheel', handleWheel);
      window.removeEventListener('resize', handleResize);
    };
  }, [data, selectedNode, onSelectNode, statusFilter]);

  return <canvas ref={canvasRef} className="w-full h-full" />;
}

/* ------------------------------------------------------------------ */
/*  Create Task Modal                                                  */
/* ------------------------------------------------------------------ */

function CreateTaskModal({
  open,
  onClose,
  onCreate,
  existingTasks,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (data: {
    name: string;
    department: string;
    priority: number;
    deadline: string;
    estimated_duration: number;
    dependencies: string[];
    description?: string;
    assigned_to?: string;
  }) => void;
  existingTasks: Task[];
}) {
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('Engineering');
  const [customDept, setCustomDept] = useState('');
  const [priority, setPriority] = useState(2);
  const [deadline, setDeadline] = useState('');
  const [estimatedDuration, setEstimatedDuration] = useState(1);
  const [dependencies, setDependencies] = useState<string[]>([]);
  const [description, setDescription] = useState('');
  const [assignedTo, setAssignedTo] = useState('');

  if (!open) return null;

  const finalDept = department === 'Other' && customDept ? customDept : department;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !deadline) return;

    // Format deadline for backend (ISO string)
    const d = new Date(deadline);
    const isoString = d.toISOString().replace('Z', '');

    onCreate({
      name: name.trim(),
      department: finalDept,
      priority,
      deadline: isoString,
      estimated_duration: estimatedDuration,
      dependencies,
      description: description.trim() || undefined,
      assigned_to: assignedTo.trim() || undefined,
    });

    // Reset
    setName('');
    setDepartment('Engineering');
    setCustomDept('');
    setPriority(2);
    setDeadline('');
    setEstimatedDuration(1);
    setDependencies([]);
    setDescription('');
    setAssignedTo('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#14141e] border border-[#252538] rounded-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-[#252538]">
          <h2 className="text-white font-semibold text-lg" style={{ fontFamily: 'Space Grotesk' }}>
            Create New Task
          </h2>
          <button onClick={onClose} className="text-[#6b6b80] hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Task Name */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Task Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter task name"
              required
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add optional task description..."
              rows={3}
              className="w-full bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 py-3 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors resize-none"
            />
          </div>

          {/* Assigned To */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Assigned To</label>
            <input
              type="text"
              value={assignedTo}
              onChange={(e) => setAssignedTo(e.target.value)}
              placeholder="e.g. John Smith"
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Department */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Department</label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors appearance-none"
            >
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            {department === 'Other' && (
              <input
                type="text"
                value={customDept}
                onChange={(e) => setCustomDept(e.target.value)}
                placeholder="Enter custom department"
                className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none mt-2"
              />
            )}
          </div>

          {/* Priority */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Priority</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4].map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPriority(p)}
                  className={`flex-1 h-11 rounded-lg text-sm font-medium transition-all ${
                    priority === p
                      ? 'text-white'
                      : 'bg-[#0a0a0f] border border-[#252538] text-[#a0a0b8] hover:text-white'
                  }`}
                  style={
                    priority === p
                      ? { backgroundColor: PRIORITY_COLORS[p], borderColor: PRIORITY_COLORS[p] }
                      : {}
                  }
                >
                  {p === 1 ? 'Low' : p === 2 ? 'Med' : p === 3 ? 'High' : 'Crit'}
                </button>
              ))}
            </div>
          </div>

          {/* Deadline */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Deadline *</label>
            <input
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              required
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Duration */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Estimated Duration (hours)</label>
            <input
              type="number"
              min={0.5}
              step={0.5}
              value={estimatedDuration}
              onChange={(e) => setEstimatedDuration(parseFloat(e.target.value) || 1)}
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Dependencies */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Dependencies</label>
            <select
              multiple
              value={dependencies}
              onChange={(e) => {
                const opts = Array.from(e.target.selectedOptions).map((o) => o.value);
                setDependencies(opts);
              }}
              className="w-full bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 py-2 text-white text-sm focus:border-[#7c6bff] focus:outline-none min-h-[80px]"
            >
              {existingTasks.map((t) => (
                <option key={t.task_id} value={t.task_id}>
                  {t.task_id} — {t.name}
                </option>
              ))}
            </select>
            <p className="text-[#6b6b80] text-xs">Hold Ctrl/Cmd to select multiple</p>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              className="flex-1 h-11 text-[#a0a0b8] hover:text-white"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="flex-1 h-11 bg-[#7c6bff] hover:bg-[#9b8fff] text-white font-medium"
            >
              Create Task
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Edit Task Modal                                                    */
/* ------------------------------------------------------------------ */

function EditTaskModal({
  open,
  onClose,
  onSave,
  task,
}: {
  open: boolean;
  onClose: () => void;
  onSave: (data: {
    name: string;
    department: string;
    priority: number;
    deadline: string;
    estimated_duration: number;
    status?: TaskStatus;
    description?: string;
    assigned_to?: string;
  }) => void;
  task: Task | null;
}) {
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('Engineering');
  const [customDept, setCustomDept] = useState('');
  const [priority, setPriority] = useState(2);
  const [deadline, setDeadline] = useState('');
  const [estimatedDuration, setEstimatedDuration] = useState(1);
  const [status, setStatus] = useState<TaskStatus>('pending');
  const [description, setDescription] = useState('');
  const [assignedTo, setAssignedTo] = useState('');

  useEffect(() => {
    if (task && open) {
      setName(task.name);
      setDepartment(task.department);
      setCustomDept('');
      setPriority(task.priority);
      setDeadline(task.deadline.split('T')[0]);
      setEstimatedDuration(task.estimated_duration);
      setStatus(task.status);
      setDescription(task.description || '');
      setAssignedTo(task.assigned_to || '');
    }
  }, [task, open]);

  if (!open || !task) return null;

  const finalDept = department === 'Other' && customDept ? customDept : department;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !deadline) return;

    const d = new Date(deadline);
    const isoString = d.toISOString().replace('Z', '');

    onSave({
      name: name.trim(),
      department: finalDept,
      priority,
      deadline: isoString,
      estimated_duration: estimatedDuration,
      status,
      description: description.trim() || undefined,
      assigned_to: assignedTo.trim() || undefined,
    });

    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#14141e] border border-[#252538] rounded-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-[#252538]">
          <h2 className="text-white font-semibold text-lg" style={{ fontFamily: 'Space Grotesk' }}>
            Edit Task
          </h2>
          <button onClick={onClose} className="text-[#6b6b80] hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Task Name */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Task Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter task name"
              required
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add optional task description..."
              rows={3}
              className="w-full bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 py-3 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors resize-none"
            />
          </div>

          {/* Assigned To */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Assigned To</label>
            <input
              type="text"
              value={assignedTo}
              onChange={(e) => setAssignedTo(e.target.value)}
              placeholder="e.g. John Smith"
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Department */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Department</label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors appearance-none"
            >
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            {department === 'Other' && (
              <input
                type="text"
                value={customDept}
                onChange={(e) => setCustomDept(e.target.value)}
                placeholder="Enter custom department"
                className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none mt-2"
              />
            )}
          </div>

          {/* Priority */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Priority</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4].map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPriority(p)}
                  className={`flex-1 h-10 rounded-lg font-semibold transition-all ${
                    priority === p
                      ? 'bg-[#7c6bff] text-white shadow-lg shadow-[#7c6bff40]'
                      : 'bg-[#0a0a0f] border border-[#252538] text-[#a0a0b8] hover:border-[#7c6bff40]'
                  }`}
                >
                  {p === 1 ? 'High' : p === 2 ? 'Medium' : p === 3 ? 'Low' : 'VeryLow'}
                </button>
              ))}
            </div>
          </div>

          {/* Status */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as TaskStatus)}
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors appearance-none"
            >
              <option value="ready">Ready</option>
              <option value="in_progress">In Progress</option>
              <option value="done">Done</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {/* Deadline */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Deadline *</label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              required
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Estimated Duration */}
          <div className="space-y-2">
            <label className="text-[#a0a0b8] text-sm font-medium">Estimated Duration (hours)</label>
            <input
              type="number"
              value={estimatedDuration}
              onChange={(e) => setEstimatedDuration(Math.max(0.5, parseFloat(e.target.value)))}
              min="0.5"
              step="0.5"
              className="w-full h-11 bg-[#0a0a0f] border border-[#252538] rounded-lg px-4 text-white text-sm focus:border-[#7c6bff] focus:outline-none focus:ring-2 focus:ring-[#7c6bff20] transition-colors"
            />
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-5">
            <Button
              type="submit"
              className="flex-1 h-11 bg-[#7c6bff] hover:bg-[#9b8fff] text-white font-semibold"
            >
              Save Changes
            </Button>
            <Button type="button" onClick={onClose} variant="outline" className="flex-1 h-11">
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Toast                                                              */
/* ------------------------------------------------------------------ */

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: string) => void }) {
  useEffect(() => {
    toasts.forEach((t) => {
      setTimeout(() => onRemove(t.id), 4000);
    });
  }, [toasts, onRemove]);

  return (
    <div className="fixed top-4 right-4 z-[100] space-y-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg min-w-[280px] animate-in slide-in-from-right-4 fade-in duration-300 ${
            t.type === 'success'
              ? 'bg-[#00e5a015] border-[#00e5a040]'
              : t.type === 'error'
              ? 'bg-[#ff5a5a15] border-[#ff5a5a40]'
              : 'bg-[#00d4ff15] border-[#00d4ff40]'
          }`}
        >
          {t.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-[#00e5a0] flex-shrink-0" />
          ) : t.type === 'error' ? (
            <AlertTriangle className="w-4 h-4 text-[#ff5a5a] flex-shrink-0" />
          ) : (
            <Zap className="w-4 h-4 text-[#00d4ff] flex-shrink-0" />
          )}
          <p
            className={`text-sm font-medium flex-1 ${
              t.type === 'success' ? 'text-[#00e5a0]' : t.type === 'error' ? 'text-[#ff5a5a]' : 'text-[#00d4ff]'
            }`}
          >
            {t.message}
          </p>
          <button onClick={() => onRemove(t.id)} className="text-[#6b6b80] hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Task Detail Panel                                                  */
/* ------------------------------------------------------------------ */

function TaskDetailPanel({
  task,
  data,
  onClose,
  onAction,
  onEdit,
}: {
  task: Task;
  data: DashboardData;
  onClose: () => void;
  onAction: (action: string, taskId: string) => void;
  onEdit: (task: Task) => void;
}) {
  const isCritical = data.critical_path.includes(task.task_id);
  const dependents = data.edges.filter((e) => e.from === task.task_id).map((e) => e.to);

  return (
    <div className="w-[360px] bg-[#14141e] border-l border-[#252538] flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#252538]">
        <span className="text-[#6b6b80] text-xs font-mono">{task.task_id}</span>
        <button onClick={onClose} className="text-[#6b6b80] hover:text-white transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="p-4 space-y-5">
        {/* Name */}
        <div>
          <h3 className="text-white font-semibold text-lg" style={{ fontFamily: 'Space Grotesk' }}>
            {task.name}
          </h3>
          <div className="flex items-center gap-2 mt-2">
            <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${STATUS_BG[task.status]}`}>
              {task.status.replace('_', ' ')}
            </span>
            <span
              className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold text-white"
              style={{ backgroundColor: PRIORITY_COLORS[task.priority] || '#7c6bff' }}
            >
              {task.priority}
            </span>
            <span className="text-[#a0a0b8] text-xs">{task.department}</span>
          </div>
        </div>

        {/* Critical Path Warning */}
        {isCritical && (
          <div className="bg-[#ff5a5a10] border-l-2 border-[#ff5a5a] rounded-r-lg p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-[#ff5a5a] mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-[#ff5a5a] text-sm font-medium">Critical Path</p>
                <p className="text-[#ff5a5a80] text-xs mt-0.5">
                  Completing this task unlocks the longest dependency chain
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Details */}
        <div className="space-y-3">
          <div className="flex items-center justify-between py-2 border-b border-[#252538]">
            <span className="text-[#a0a0b8] text-sm">Deadline</span>
            <span className="text-white text-sm font-mono">
              {new Date(task.deadline).toLocaleString()}
            </span>
          </div>

          {/* Late Completion Warning */}
          {task.status === 'done' && task.completed_at && (
            (() => {
              const deadlineDate = new Date(task.deadline);
              const completedDate = new Date(task.completed_at);
              const isLate = completedDate > deadlineDate;
              const hoursLate = isLate ? ((completedDate.getTime() - deadlineDate.getTime()) / (1000 * 60 * 60)).toFixed(1) : 0;
              
              return isLate ? (
                <div className="bg-[#ff5a5a10] border-l-2 border-[#ff5a5a] rounded-r-lg p-3">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-[#ff5a5a] mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-[#ff5a5a] text-sm font-medium">Completed Late</p>
                      <p className="text-[#ff5a5a80] text-xs mt-0.5">
                        Passed deadline by {hoursLate}h • Completed {completedDate.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              ) : null;
            })()
          )}

          <div className="flex items-center justify-between py-2 border-b border-[#252538]">
            <span className="text-[#a0a0b8] text-sm">Duration</span>
            <span className="text-white text-sm">{task.estimated_duration}h</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-[#252538]">
            <span className="text-[#a0a0b8] text-sm">Base Priority</span>
            <span className="text-white text-sm font-medium">{task.base_priority}</span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-[#252538]">
            <span className="text-[#a0a0b8] text-sm">Wait Time</span>
            <span className="text-[#7c6bff] text-sm font-mono">
              {task.wait_time.toFixed(1)}h
            </span>
          </div>
          {task.delay !== undefined && task.delay !== null && (
            <div className="flex items-center justify-between py-2 border-b border-[#252538]">
              <span className="text-[#a0a0b8] text-sm">Delay</span>
              <span className="text-[#ff5a5a] text-sm font-mono">{task.delay.toFixed(1)}h</span>
            </div>
          )}
        </div>

        {/* Dependencies */}
        {task.dependencies.length > 0 && (
          <div>
            <h4 className="text-[#a0a0b8] text-xs uppercase tracking-wider mb-2">Dependencies</h4>
            <div className="flex flex-wrap gap-1.5">
              {task.dependencies.map((dep) => (
                <span
                  key={dep}
                  className="text-xs bg-[#0a0a0f] border border-[#252538] text-[#a0a0b8] px-2 py-1 rounded font-mono"
                >
                  {dep}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Dependents */}
        {dependents.length > 0 && (
          <div>
            <h4 className="text-[#a0a0b8] text-xs uppercase tracking-wider mb-2">Dependents</h4>
            <div className="flex flex-wrap gap-1.5">
              {dependents.map((dep) => (
                <span
                  key={dep}
                  className="text-xs bg-[#0a0a0f] border border-[#252538] text-[#a0a0b8] px-2 py-1 rounded font-mono"
                >
                  {dep}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="space-y-2 pt-2">
          <Button
            onClick={() => onEdit(task)}
            variant="ghost"
            className="w-full h-10 text-[#7c6bff] hover:text-[#9b8fff] hover:bg-[#7c6bff15]"
          >
            <Edit className="w-4 h-4 mr-2" />
            Edit Task
          </Button>
          {task.status === 'ready' && (
            <Button
              onClick={() => onAction('start', task.task_id)}
              className="w-full h-10 bg-[#7c6bff] hover:bg-[#9b8fff] text-white font-medium"
            >
              <Play className="w-4 h-4 mr-2" />
              Start Task
            </Button>
          )}
          {task.status === 'in_progress' && (
            <Button
              onClick={() => onAction('complete', task.task_id)}
              className="w-full h-10 bg-[#00e5a0] hover:bg-[#33eab3] text-[#0a0a0f] font-medium"
            >
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Complete Task
            </Button>
          )}
          {(task.status === 'pending' || task.status === 'ready' || task.status === 'in_progress') && (
            <Button
              onClick={() => onAction('cancel', task.task_id)}
              variant="ghost"
              className="w-full h-10 text-[#ff5a5a] hover:text-[#ff5a5a] hover:bg-[#ff5a5a15]"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Cancel Task
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Dashboard                                                     */
/* ------------------------------------------------------------------ */

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'queue' | 'tasks' | 'history' | 'create'>('queue');
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | null>(null);
  const [taskStatusFilter, setTaskStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const addToast = useCallback((message: string, type: Toast['type']) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const loadDashboard = useCallback(async () => {
    try {
      const d = await getDashboard();
      setData(d);
    } catch (err: any) {
      addToast(err.message || 'Failed to load dashboard', 'error');
      if (err.message?.includes('auth') || err.message?.includes('login')) {
        navigate('/signin');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate, addToast]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const handleCreateTask = async (taskData: Parameters<typeof createTask>[0]) => {
    try {
      await createTask(taskData);
      addToast('Task created successfully', 'success');
      loadDashboard();
    } catch (err: any) {
      addToast(err.message || 'Failed to create task', 'error');
    }
  };

  const handleEditTask = async (taskData: Parameters<typeof updateTask>[1]) => {
    if (!editingTask) return;
    try {
      await updateTask(editingTask.task_id, taskData);
      addToast('Task updated successfully', 'success');
      setEditingTask(null);
      setSelectedNode(null);
      loadDashboard();
    } catch (err: any) {
      addToast(err.message || 'Failed to update task', 'error');
    }
  };

  const handleAction = async (action: string, taskId: string) => {
    try {
      if (action === 'start') {
        await startNextTask();
        addToast(`Started ${taskId}`, 'success');
      } else if (action === 'complete') {
        await completeTask(taskId);
        addToast(`Completed ${taskId}`, 'success');
      } else if (action === 'cancel') {
        await cancelTask(taskId);
        addToast(`Cancelled ${taskId}`, 'info');
      }
      setSelectedNode(null);
      loadDashboard();
    } catch (err: any) {
      addToast(err.message || 'Action failed', 'error');
    }
  };

  const handleRebalance = async () => {
    try {
      await rebalanceQueue();
      addToast('Queue rebalanced', 'success');
      loadDashboard();
    } catch (err: any) {
      addToast(err.message || 'Rebalance failed', 'error');
    }
  };

  const handleStartNext = async () => {
    try {
      await startNextTask();
      addToast('Started next task', 'success');
      loadDashboard();
    } catch (err: any) {
      addToast(err.message || 'No ready tasks', 'error');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Spinner className="w-10 h-10 text-[#7c6bff]" />
          <p className="text-[#a0a0b8] text-sm">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="text-center">
          <p className="text-[#ff5a5a] mb-4">Failed to load dashboard</p>
          <Button onClick={loadDashboard} className="bg-[#7c6bff] hover:bg-[#9b8fff] text-white">
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const selectedTask = selectedNode ? data.tasks.find((t) => t.task_id === selectedNode) : null;

  const filteredTasks =
    taskStatusFilter === 'all'
      ? data.tasks
      : data.tasks.filter((t) => {
          if (taskStatusFilter === 'delayed') return t.status === 'delayed';
          return t.status === taskStatusFilter;
        });

  const searchedTasks = searchQuery
    ? filteredTasks.filter(
        (t) =>
          t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          t.task_id.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : filteredTasks;

  return (
    <div className="h-screen bg-[#0a0a0f] flex flex-col overflow-hidden">
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      {/* ── Top Bar ── */}
      <header className="h-14 bg-[#14141e] border-b border-[#252538] flex items-center justify-between px-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Network className="w-5 h-5 text-[#7c6bff]" />
            <span className="text-white font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
              FlowDesk
            </span>
          </div>
          <span className="text-[#6b6b80] text-xs">Dashboard</span>
        </div>

        <div className="hidden md:flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6b6b80]" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-64 h-9 bg-[#0a0a0f] border border-[#252538] rounded-lg pl-9 pr-4 text-white text-sm placeholder:text-[#6b6b80] focus:border-[#7c6bff] focus:outline-none"
            />
          </div>

          <Button
            onClick={handleRebalance}
            variant="outline"
            size="sm"
            className="border-[#7c6bff] text-[#7c6bff] hover:bg-[#7c6bff15] h-9 text-xs"
          >
            <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
            Rebalance
          </Button>

          <Button
            onClick={handleStartNext}
            size="sm"
            className="bg-[#7c6bff] hover:bg-[#9b8fff] text-white h-9 text-xs"
          >
            <Play className="w-3.5 h-3.5 mr-1.5" />
            Start Next
          </Button>
        </div>

        <div className="flex items-center gap-3">
          {/* User */}
          <div className="hidden sm:flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#7c6bff] to-[#00d4ff] flex items-center justify-center text-white text-xs font-semibold">
              {user?.full_name?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="hidden lg:block">
              <p className="text-white text-xs font-medium">{user?.full_name || 'User'}</p>
              <p className="text-[#6b6b80] text-[10px] font-mono">{user?.email}</p>
            </div>
          </div>

          <Button
            onClick={() => {
              logout();
              navigate('/');
            }}
            variant="ghost"
            size="sm"
            className="text-[#a0a0b8] hover:text-white h-9"
          >
            <LogOut className="w-4 h-4" />
          </Button>
        </div>
      </header>

      {/* ── Main Content ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Sidebar ── */}
        <aside className="w-[280px] bg-[#14141e] border-r border-[#252538] flex flex-col flex-shrink-0">
          {/* User Section */}
          <div className="p-4 border-b border-[#252538]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#7c6bff] to-[#00d4ff] flex items-center justify-center text-white font-semibold">
                {user?.full_name?.[0]?.toUpperCase() || 'U'}
              </div>
              <div>
                <p className="text-white text-sm font-medium">{user?.full_name || 'User'}</p>
                <p className="text-[#6b6b80] text-xs font-mono truncate max-w-[180px]">
                  {user?.email}
                </p>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <nav className="flex-1 overflow-y-auto p-2 space-y-1">
            <button
              onClick={() => setActiveTab('queue')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'queue'
                  ? 'bg-[#1e1e2d] text-white border-l-[3px] border-[#7c6bff]'
                  : 'text-[#a0a0b8] hover:bg-[#1e1e2d] hover:text-white'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              Queue
              {data.queue.length > 0 && (
                <span className="ml-auto text-[#7c6bff] text-xs font-mono">{data.queue.length}</span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('tasks')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'tasks'
                  ? 'bg-[#1e1e2d] text-white border-l-[3px] border-[#7c6bff]'
                  : 'text-[#a0a0b8] hover:bg-[#1e1e2d] hover:text-white'
              }`}
            >
              <List className="w-4 h-4" />
              All Tasks
              <span className="ml-auto text-[#6b6b80] text-xs font-mono">{data.tasks.length}</span>
            </button>

            <button
              onClick={() => setActiveTab('history')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'history'
                  ? 'bg-[#1e1e2d] text-white border-l-[3px] border-[#7c6bff]'
                  : 'text-[#a0a0b8] hover:bg-[#1e1e2d] hover:text-white'
              }`}
            >
              <History className="w-4 h-4" />
              History
              <span className="ml-auto text-[#6b6b80] text-xs font-mono">{data.history.length}</span>
            </button>

            <button
              onClick={() => setShowCreateModal(true)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'create'
                  ? 'bg-[#1e1e2d] text-white border-l-[3px] border-[#7c6bff]'
                  : 'text-[#a0a0b8] hover:bg-[#1e1e2d] hover:text-white'
              }`}
            >
              <Plus className="w-4 h-4" />
              Create Task
            </button>

            {/* Stats */}
            <div className="mt-6 pt-4 border-t border-[#252538] px-3">
              <h4 className="text-[#6b6b80] text-xs uppercase tracking-wider mb-3">Overview</h4>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-[#0a0a0f] rounded-lg p-3">
                  <p className="text-[#00e5a0] text-lg font-semibold">{data.stats.completed}</p>
                  <p className="text-[#6b6b80] text-xs">Completed</p>
                </div>
                <div className="bg-[#0a0a0f] rounded-lg p-3">
                  <p className="text-[#ff5a5a] text-lg font-semibold">{data.stats.cancelled}</p>
                  <p className="text-[#6b6b80] text-xs">Cancelled</p>
                </div>
                <div className="bg-[#0a0a0f] rounded-lg p-3 col-span-2">
                  <p className="text-[#a0a0b8] text-lg font-semibold">
                    {data.avg_delay ? `${data.avg_delay.toFixed(1)}h` : '0h'}
                  </p>
                  <p className="text-[#6b6b80] text-xs">Avg Delay</p>
                </div>
              </div>
            </div>

            {/* Critical Path Info */}
            {data.critical_path.length > 0 && (
              <div className="mt-4 px-3">
                <div className="bg-[#ff5a5a10] border border-[#ff5a5a30] rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <GitBranch className="w-3.5 h-3.5 text-[#ff5a5a]" />
                    <span className="text-[#ff5a5a] text-xs font-medium">Critical Path</span>
                  </div>
                  <p className="text-[#ff5a5a80] text-xs">
                    {data.critical_path.length} tasks · {data.critical_duration.toFixed(1)}h
                  </p>
                </div>
              </div>
            )}
          </nav>
        </aside>

        {/* ── Graph Area ── */}
        <main className="flex-1 relative">
          <GraphCanvas
            data={data}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
            statusFilter={activeTab === 'queue' ? null : statusFilter}
          />

          {/* Status Legend (top-right) */}
          <div className="absolute top-4 right-4 bg-[#14141e]/90 backdrop-blur-sm border border-[#252538] rounded-lg p-4">
            <h4 className="text-[#a0a0b8] text-xs uppercase tracking-wider font-semibold mb-3">Task Status</h4>
            <div className="space-y-2">
              {(['pending', 'ready', 'in_progress', 'done', 'delayed'] as const).map((s) => (
                <div key={s} className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: STATUS_COLORS[s] }}
                  />
                  <span className="text-[#a0a0b8] text-xs capitalize">{s.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Status filter overlay (bottom) */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 bg-[#14141e]/90 backdrop-blur-sm border border-[#252538] rounded-lg px-3 py-2">
            <Filter className="w-3.5 h-3.5 text-[#6b6b80] mr-1" />
            {(['all', 'pending', 'ready', 'in_progress', 'done', 'delayed'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s === 'all' ? null : (s as TaskStatus))}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                  (s === 'all' && !statusFilter) || statusFilter === s
                    ? 'bg-[#7c6bff] text-white'
                    : 'text-[#a0a0b8] hover:bg-[#1e1e2d]'
                }`}
              >
                {s === 'all' ? 'All' : s.replace('_', ' ')}
              </button>
            ))}
          </div>

          {/* Sidebar panels overlay */}
          {activeTab === 'queue' && (
            <div className="absolute top-4 left-4 w-72 bg-[#14141e]/95 backdrop-blur-sm border border-[#252538] rounded-xl max-h-[calc(100%-80px)] overflow-y-auto">
              <div className="p-4 border-b border-[#252538]">
                <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-[#7c6bff]" />
                  Ready Queue
                </h3>
                <p className="text-[#6b6b80] text-xs mt-0.5">Top tasks by effective priority</p>
              </div>
              <div className="p-2 space-y-1">
                {data.queue.length === 0 ? (
                  <div className="p-4 text-center">
                    <p className="text-[#6b6b80] text-sm">No ready tasks</p>
                  </div>
                ) : (
                  data.queue.slice(0, 10).map((task) => (
                    <button
                      key={task.task_id}
                      onClick={() => setSelectedNode(task.task_id)}
                      className={`w-full text-left p-3 rounded-lg transition-all ${
                        selectedNode === task.task_id
                          ? 'bg-[#7c6bff20] border border-[#7c6bff40]'
                          : 'hover:bg-[#1e1e2d] border border-transparent'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[#6b6b80] text-[10px] font-mono">{task.task_id}</span>
                        <span
                          className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold text-white"
                          style={{ backgroundColor: PRIORITY_COLORS[task.priority] || '#7c6bff' }}
                        >
                          {task.priority}
                        </span>
                      </div>
                      <p className="text-white text-sm font-medium truncate">{task.name}</p>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-[#6b6b80] text-xs">{task.department}</span>
                        <span className="text-[#7c6bff] text-xs font-mono">
                          EP: {task.effective_priority?.toFixed(1) || task.priority}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {activeTab === 'tasks' && (
            <div className="absolute top-4 left-4 w-80 bg-[#14141e]/95 backdrop-blur-sm border border-[#252538] rounded-xl max-h-[calc(100%-80px)] overflow-y-auto">
              <div className="p-4 border-b border-[#252538]">
                <h3 className="text-white font-semibold text-sm">All Tasks</h3>
                {/* Status filter tabs */}
                <div className="flex gap-1 mt-2 flex-wrap">
                  {(['all', 'pending', 'ready', 'in_progress', 'done', 'delayed'] as const).map(
                    (s) => (
                      <button
                        key={s}
                        onClick={() => setTaskStatusFilter(s)}
                        className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${
                          taskStatusFilter === s
                            ? 'bg-[#7c6bff] text-white'
                            : 'text-[#6b6b80] hover:text-[#a0a0b8] bg-[#0a0a0f]'
                        }`}
                      >
                        {s === 'all' ? 'All' : s.replace('_', ' ')}
                      </button>
                    )
                  )}
                </div>
              </div>
              <div className="p-2 space-y-1">
                {searchedTasks.length === 0 ? (
                  <div className="p-4 text-center">
                    <p className="text-[#6b6b80] text-sm">No tasks found</p>
                  </div>
                ) : (
                  searchedTasks.map((task) => (
                    <button
                      key={task.task_id}
                      onClick={() => setSelectedNode(task.task_id)}
                      className={`w-full text-left p-3 rounded-lg transition-all ${
                        selectedNode === task.task_id
                          ? 'bg-[#7c6bff20] border border-[#7c6bff40]'
                          : 'hover:bg-[#1e1e2d] border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ backgroundColor: STATUS_COLORS[task.status] }}
                        />
                        <span className="text-[#6b6b80] text-[10px] font-mono">{task.task_id}</span>
                        <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded-full ${STATUS_BG[task.status]}`}>
                          {task.status.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-white text-sm font-medium truncate">{task.name}</p>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-[#6b6b80] text-xs">{task.department}</span>
                        <span className="text-[#6b6b80] text-xs font-mono">
                          {new Date(task.deadline).toLocaleDateString()}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {activeTab === 'history' && (
            <div className="absolute top-4 left-4 w-80 bg-[#14141e]/95 backdrop-blur-sm border border-[#252538] rounded-xl max-h-[calc(100%-80px)] overflow-y-auto">
              <div className="p-4 border-b border-[#252538]">
                <h3 className="text-white font-semibold text-sm flex items-center gap-2">
                  <History className="w-4 h-4 text-[#a0a0b8]" />
                  Task History
                </h3>
              </div>
              <div className="p-2 space-y-1">
                {data.history.length === 0 ? (
                  <div className="p-4 text-center">
                    <p className="text-[#6b6b80] text-sm">No history yet</p>
                  </div>
                ) : (
                  data.history.map((task) => (
                    <div
                      key={task.task_id + task.completed_at}
                      className="p-3 rounded-lg hover:bg-[#1e1e2d] transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {task.status === 'done' ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#00e5a0]" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-[#6b6b80]" />
                        )}
                        <span className="text-white text-sm font-medium truncate">{task.name}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className={`text-xs ${STATUS_BG[task.status]}`}>
                          {task.status}
                        </span>
                        {task.delay !== undefined && task.delay !== null && task.delay > 0 && (
                          <span className="text-[#ff5a5a] text-xs font-mono">
            +{task.delay.toFixed(1)}h
                          </span>
                        )}
                      </div>
                      {task.completed_at && (
                        <p className="text-[#6b6b80] text-[10px] mt-1 font-mono">
                          {new Date(task.completed_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </main>

        {/* ── Task Detail Panel ── */}
        {selectedTask && (
          <TaskDetailPanel
            task={selectedTask}
            data={data}
            onClose={() => setSelectedNode(null)}
            onAction={handleAction}
            onEdit={(task) => {
              setEditingTask(task);
              setShowEditModal(true);
            }}
          />
        )}
      </div>

      {/* ── Create Task Modal ── */}
      <CreateTaskModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateTask}
        existingTasks={data.tasks.filter((t) => t.status !== 'cancelled' && t.status !== 'done')}
      />

      {/* ── Edit Task Modal ── */}
      <EditTaskModal
        open={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingTask(null);
        }}
        onSave={handleEditTask}
        task={editingTask}
      />
    </div>
  );
}
