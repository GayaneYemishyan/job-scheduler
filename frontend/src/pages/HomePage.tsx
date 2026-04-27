import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import {
  Layers,
  Shield,
  Network,
  ArrowRight,
  ChevronDown,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

/* ------------------------------------------------------------------ */
/*  Hero Graph Canvas                                                  */
/* ------------------------------------------------------------------ */

interface SimNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  radius: number;
  status: string;
  label: string;
}

interface SimEdge {
  from: string;
  to: string;
  isCritical: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#4a4a5e',
  ready: '#7c6bff',
  in_progress: '#00d4ff',
  done: '#00e5a0',
  delayed: '#ff5a5a',
  cancelled: '#6b6b80',
};

function generateSampleGraph(): { nodes: SimNode[]; edges: SimEdge[] } {
  const nodes: SimNode[] = [];
  const edges: SimEdge[] = [];
  const statuses = ['pending', 'ready', 'in_progress', 'done', 'delayed'];
  const names = [
    'Design System', 'API Integration', 'User Auth', 'Database Setup',
    'Frontend Build', 'Testing Suite', 'Deployment', 'Monitoring',
    'Documentation', 'Code Review', 'CI/CD Pipeline', 'Performance Opt',
    'Security Audit', 'User Testing', 'Bug Fixes',
  ];

  for (let i = 0; i < 25; i++) {
    const angle = (i / 25) * Math.PI * 2;
    const r = 100 + Math.random() * 200;
    nodes.push({
      id: `T${(i + 1).toString().padStart(4, '0')}`,
      x: Math.cos(angle) * r + window.innerWidth / 2,
      y: Math.sin(angle) * r + window.innerHeight / 2,
      vx: 0,
      vy: 0,
      color: STATUS_COLORS[statuses[i % statuses.length]],
      radius: 6 + Math.random() * 8,
      status: statuses[i % statuses.length],
      label: names[i % names.length],
    });
  }

  for (let i = 0; i < nodes.length; i++) {
    const numDeps = Math.floor(Math.random() * 3);
    for (let d = 0; d < numDeps; d++) {
      const target = Math.floor(Math.random() * nodes.length);
      if (target !== i) {
        edges.push({
          from: nodes[i].id,
          to: nodes[target].id,
          isCritical: Math.random() < 0.15,
        });
      }
    }
  }

  return { nodes, edges };
}

function HeroGraph() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const graphRef = useRef<{ nodes: SimNode[]; edges: SimEdge[] } | null>(null);

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

    if (!graphRef.current) {
      graphRef.current = generateSampleGraph();
    }
    const { nodes, edges } = graphRef.current;

    let animId: number;
    let time = 0;

    function animate() {
      time += 0.016;
      ctx!.clearRect(0, 0, w, h);

      // Center gravity
      const cx = w / 2;
      const cy = h / 2;

      nodes.forEach((node) => {
        // Gentle floating motion
        node.vx += (cx - node.x) * 0.0001 + Math.sin(time + parseInt(node.id.slice(1))) * 0.01;
        node.vy += (cy - node.y) * 0.0001 + Math.cos(time + parseInt(node.id.slice(1))) * 0.01;

        // Repulsion from other nodes
        nodes.forEach((other) => {
          if (node.id === other.id) return;
          const dx = node.x - other.x;
          const dy = node.y - other.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          if (dist < 150) {
            const force = 20 / (dist * dist);
            node.vx += (dx / dist) * force;
            node.vy += (dy / dist) * force;
          }
        });

        // Spring force along edges
        edges.forEach((edge) => {
          if (edge.from === node.id) {
            const other = nodes.find((n) => n.id === edge.to);
            if (other) {
              const dx = other.x - node.x;
              const dy = other.y - node.y;
              const dist = Math.sqrt(dx * dx + dy * dy) || 1;
              const force = (dist - 120) * 0.001;
              node.vx += (dx / dist) * force;
              node.vy += (dy / dist) * force;
            }
          }
        });

        node.vx *= 0.92;
        node.vy *= 0.92;
        node.x += node.vx;
        node.y += node.vy;

        // Bounds
        node.x = Math.max(50, Math.min(w - 50, node.x));
        node.y = Math.max(50, Math.min(h - 50, node.y));
      });

      // Draw edges
      edges.forEach((edge) => {
        const from = nodes.find((n) => n.id === edge.from);
        const to = nodes.find((n) => n.id === edge.to);
        if (!from || !to) return;

        ctx!.beginPath();
        ctx!.moveTo(from.x, from.y);
        ctx!.lineTo(to.x, to.y);
        if (edge.isCritical) {
          ctx!.strokeStyle = '#ff5a5a';
          ctx!.lineWidth = 1.5;
          ctx!.setLineDash([5, 5]);
          ctx!.shadowColor = '#ff5a5a';
          ctx!.shadowBlur = 8;
        } else {
          ctx!.strokeStyle = 'rgba(58, 58, 78, 0.5)';
          ctx!.lineWidth = 0.8;
          ctx!.setLineDash([]);
          ctx!.shadowBlur = 0;
        }
        ctx!.stroke();
        ctx!.setLineDash([]);
        ctx!.shadowBlur = 0;
      });

      // Draw nodes
      nodes.forEach((node) => {
        const isHovered = hovered === node.id;
        const scale = isHovered ? 1.5 : 1;

        // Glow
        if (node.status === 'ready' || node.status === 'in_progress' || node.status === 'delayed') {
          ctx!.beginPath();
          ctx!.arc(node.x, node.y, node.radius * scale * 2.5, 0, Math.PI * 2);
          ctx!.fillStyle = node.color + '15';
          ctx!.fill();
        }

        // Node circle
        ctx!.beginPath();
        ctx!.arc(node.x, node.y, node.radius * scale, 0, Math.PI * 2);
        ctx!.fillStyle = node.color;
        ctx!.fill();

        // Border
        ctx!.strokeStyle = isHovered ? '#ffffff' : node.color + '80';
        ctx!.lineWidth = isHovered ? 2 : 1;
        ctx!.stroke();

        // Label on hover or for active tasks
        if (isHovered || node.status === 'ready' || node.status === 'in_progress') {
          ctx!.font = '500 11px Inter, sans-serif';
          ctx!.fillStyle = '#ffffff';
          ctx!.textAlign = 'center';
          ctx!.textBaseline = 'bottom';
          ctx!.shadowColor = '#0a0a0f';
          ctx!.shadowBlur = 4;
          ctx!.fillText(node.label, node.x, node.y - node.radius * scale - 6);
          ctx!.shadowBlur = 0;
        }
      });

      animId = requestAnimationFrame(animate);
    }

    animate();

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };

      let closest: string | null = null;
      let closestDist = Infinity;
      nodes.forEach((node) => {
        const dx = mouseRef.current.x - node.x;
        const dy = mouseRef.current.y - node.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < node.radius + 10 && dist < closestDist) {
          closest = node.id;
          closestDist = dist;
        }
      });
      setHovered(closest);
    };

    canvas.addEventListener('mousemove', handleMouseMove);

    const handleResize = () => {
      w = canvas.offsetWidth;
      h = canvas.offsetHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      canvas.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
    };
  }, [hovered]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full cursor-crosshair"
      style={{ opacity: 0.7 }}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Navigation                                                         */
/* ------------------------------------------------------------------ */

function Navigation() {
  const { user } = useAuth();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 100);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 h-16 flex items-center justify-between px-6 lg:px-12 transition-all duration-200 ${
        scrolled ? 'bg-[#0a0a0f]/90 backdrop-blur-xl' : 'bg-transparent'
      }`}
    >
      <Link to="/" className="flex items-center gap-2">
        <Network className="w-6 h-6 text-[#7c6bff]" />
        <span className="text-white font-semibold text-lg" style={{ fontFamily: 'Space Grotesk' }}>
          FlowDesk
        </span>
      </Link>

      <div className="hidden md:flex items-center gap-8">
        <button
          onClick={() => scrollToSection('features')}
          className="text-[#a0a0b8] hover:text-white text-sm font-medium transition-colors"
        >
          Features
        </button>
        <button
          onClick={() => scrollToSection('how-it-works')}
          className="text-[#a0a0b8] hover:text-white text-sm font-medium transition-colors"
        >
          How It Works
        </button>
      </div>

      <div className="flex items-center gap-3">
        {user ? (
          <Link to="/dashboard">
            <Button className="bg-[#7c6bff] hover:bg-[#9b8fff] text-white h-9 px-5 text-sm font-medium">
              Dashboard
            </Button>
          </Link>
        ) : (
          <>
            <Link to="/signin" className="hidden sm:block">
              <Button variant="ghost" className="text-[#a0a0b8] hover:text-white h-9 px-4 text-sm">
                Sign In
              </Button>
            </Link>
            <Link to="/signup">
              <Button className="bg-[#7c6bff] hover:bg-[#9b8fff] text-white h-9 px-5 text-sm font-medium">
                Get Started
              </Button>
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/*  Feature Card                                                       */
/* ------------------------------------------------------------------ */

function FeatureCard({
  icon: Icon,
  title,
  description,
  accent,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  accent: string;
}) {
  return (
    <div className="group bg-[#14141e] border border-[#252538] rounded-xl p-6 hover:border-[#7c6bff40] hover:-translate-y-1 transition-all duration-200">
      <div
        className="w-12 h-12 rounded-lg flex items-center justify-center mb-4"
        style={{ backgroundColor: accent + '15' }}
      >
        <Icon className="w-6 h-6" style={{ color: accent }} />
      </div>
      <h4 className="text-white font-semibold text-lg mb-2" style={{ fontFamily: 'Space Grotesk' }}>
        {title}
      </h4>
      <p className="text-[#a0a0b8] text-sm leading-relaxed">{description}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  How It Works Step                                                  */
/* ------------------------------------------------------------------ */

function StepCard({
  number,
  title,
  description,
  items,
  reverse,
}: {
  number: string;
  title: string;
  description: string;
  items: string[];
  reverse?: boolean;
}) {
  return (
    <div className={`flex flex-col ${reverse ? 'lg:flex-row-reverse' : 'lg:flex-row'} gap-8 lg:gap-16 items-center`}>
      <div className="flex-1">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-[#7c6bff20] text-[#7c6bff] text-sm font-semibold mb-4">
          {number}
        </div>
        <h3 className="text-white font-semibold text-2xl lg:text-3xl mb-4" style={{ fontFamily: 'Space Grotesk' }}>
          {title}
        </h3>
        <p className="text-[#a0a0b8] text-base leading-relaxed mb-6">{description}</p>
        <ul className="space-y-3">
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-3 text-[#a0a0b8] text-sm">
              <Zap className="w-4 h-4 text-[#7c6bff] mt-0.5 flex-shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex-1 w-full">
        <div className="bg-[#14141e] border border-[#252538] rounded-xl p-6 lg:p-8">
          <div className="space-y-4">
            {items.map((item, i) => (
              <div
                key={i}
                className="flex items-center gap-4 p-4 rounded-lg bg-[#0a0a0f] border border-[#252538]"
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0"
                  style={{
                    backgroundColor: ['#7c6bff20', '#00d4ff20', '#00e5a020', '#ffb34720'][i % 4],
                    color: ['#7c6bff', '#00d4ff', '#00e5a0', '#ffb347'][i % 4],
                  }}
                >
                  {i + 1}
                </div>
                <span className="text-white text-sm">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Home Page                                                          */
/* ------------------------------------------------------------------ */

export default function HomePage() {
  const heroRef = useRef<HTMLDivElement>(null);
  const [heroVisible, setHeroVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setHeroVisible(true), 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <Navigation />

      {/* ── Hero ── */}
      <section ref={heroRef} className="relative min-h-screen flex items-end overflow-hidden">
        <HeroGraph />

        <div className="absolute inset-0 bg-gradient-to-t from-[#0a0a0f] via-[#0a0a0f]/40 to-transparent pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0a0a0f]/90 via-[#0a0a0f]/50 to-transparent pointer-events-none" />

        <div
          className={`relative z-10 px-6 lg:px-16 pb-20 lg:pb-24 max-w-xl transition-all duration-700 ${
            heroVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <h1
            className="text-5xl lg:text-6xl font-semibold text-white mb-4 tracking-tight"
            style={{ fontFamily: 'Space Grotesk', letterSpacing: '-0.03em' }}
          >
            FlowDesk
          </h1>
          <p className="text-[#a0a0b8] text-lg leading-relaxed mb-8">
            Priority-driven task scheduling with intelligent dependency management. Never miss a
            deadline, never starve a task.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link to="/signup">
              <Button className="bg-[#7c6bff] hover:bg-[#9b8fff] text-white h-12 px-8 text-base font-medium transition-all hover:-translate-y-0.5">
                Start Scheduling
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <button
              onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
              className="h-12 px-6 text-[#a0a0b8] hover:text-white text-sm font-medium transition-colors flex items-center gap-2"
            >
              Learn More
              <ChevronDown className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="relative py-24 lg:py-32 px-6 lg:px-16">
        <div className="absolute inset-0 opacity-[0.03]">
          <svg width="100%" height="100%">
            <defs>
              <pattern id="hex" width="40" height="40" patternUnits="userSpaceOnUse">
                <path
                  d="M20 0 L40 10 L40 30 L20 40 L0 30 L0 10 Z"
                  fill="none"
                  stroke="#ffffff"
                  strokeWidth="0.5"
                />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#hex)" />
          </svg>
        </div>

        <div className="relative max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2
              className="text-3xl lg:text-4xl font-semibold text-white mb-4"
              style={{ fontFamily: 'Space Grotesk', letterSpacing: '-0.02em' }}
            >
              Built for Complex Workflows
            </h2>
            <p className="text-[#a0a0b8] text-base max-w-xl mx-auto">
              Custom data structures and algorithms designed from scratch for maximum scheduling
              efficiency
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard
              icon={Layers}
              title="Priority Intelligence"
              description="Binary max-heap with heap-map gives O(log n) extraction. Critical path detection adds priority boosts to bottleneck tasks."
              accent="#7c6bff"
            />
            <FeatureCard
              icon={Shield}
              title="Anti-Starvation Protection"
              description="Long-waiting tasks gradually gain effective priority. A task waiting 10 hours gains 1 full priority unit — no task is left behind."
              accent="#00d4ff"
            />
            <FeatureCard
              icon={Network}
              title="Live Dependency Graph"
              description="Interactive force-directed graph shows real-time task states. Pan, zoom, and click nodes for instant details. Critical path highlighted in red."
              accent="#00e5a0"
            />
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section id="how-it-works" className="py-24 lg:py-32 px-6 lg:px-16">
        <div className="max-w-5xl mx-auto space-y-24">
          <div className="text-center">
            <h2
              className="text-3xl lg:text-4xl font-semibold text-white mb-4"
              style={{ fontFamily: 'Space Grotesk', letterSpacing: '-0.02em' }}
            >
              How It Works
            </h2>
            <p className="text-[#a0a0b8] text-base max-w-xl mx-auto">
              From submission to completion — a streamlined workflow powered by intelligent algorithms
            </p>
          </div>

          <StepCard
            number="1"
            title="Submit Tasks with Dependencies"
            description="Create tasks with priorities, deadlines, and dependencies. The scheduler validates against cycles using DFS detection."
            items={[
              'Define task name, department, and deadline',
              'Set priority level from Low to Critical',
              'Add dependencies on existing tasks',
              'Automatic cycle detection prevents invalid graphs',
            ]}
          />

          <StepCard
            number="2"
            title="Smart Scheduling"
            description="Tasks with satisfied dependencies enter the ready queue. The heap always serves the highest effective-priority task."
            items={[
              'Topological sort determines task readiness',
              'Max-heap orders by effective priority',
              'Critical path tasks get priority boosts',
              'Anti-starvation ensures fair scheduling',
            ]}
            reverse
          />

          <StepCard
            number="3"
            title="Real-Time Tracking"
            description="Complete tasks to unlock dependents. Monitor the critical path. Rebalance the queue to prevent starvation."
            items={[
              'Visual dependency graph updates live',
              'Status colors show task state at a glance',
              'Complete tasks to unlock dependents',
              'Rebalance to refresh priorities over time',
            ]}
          />
        </div>
      </section>

      {/* ── Stats / CTA ── */}
      <section className="py-20 px-6 lg:px-16">
        <div className="max-w-4xl mx-auto bg-gradient-to-br from-[#14141e] to-[#1e1e2d] border border-[#252538] rounded-2xl p-10 lg:p-16 text-center">
          <h2
            className="text-3xl lg:text-4xl font-semibold text-white mb-6"
            style={{ fontFamily: 'Space Grotesk', letterSpacing: '-0.02em' }}
          >
            Ready to Optimize Your Workflow?
          </h2>
          <p className="text-[#a0a0b8] text-base mb-8 max-w-lg mx-auto">
            Join teams using FlowDesk to manage complex task dependencies with intelligent priority
            scheduling.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link to="/signup">
              <Button className="bg-[#7c6bff] hover:bg-[#9b8fff] text-white h-12 px-8 text-base font-medium transition-all hover:-translate-y-0.5">
                Get Started Free
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/signin">
              <Button
                variant="outline"
                className="border-[#7c6bff] text-[#7c6bff] hover:bg-[#7c6bff15] h-12 px-8 text-base font-medium"
              >
                Sign In
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-[#252538] px-6 lg:px-16 py-8">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Network className="w-5 h-5 text-[#7c6bff]" />
            <span className="text-white font-semibold" style={{ fontFamily: 'Space Grotesk' }}>
              FlowDesk
            </span>
          </div>
          <span className="text-[#6b6b80] text-xs" style={{ fontFamily: 'JetBrains Mono' }}>
            Built with custom data structures — Directed Acyclic Graph, Binary Max-Heap, Open-addressing Hash Map
          </span>
        </div>
      </footer>
    </div>
  );
}
