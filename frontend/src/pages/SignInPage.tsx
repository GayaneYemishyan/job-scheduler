import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import { Network, ArrowLeft, Eye, EyeOff } from 'lucide-react';

export default function SignInPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await signIn(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center px-4">
      {/* Background pattern */}
      <div className="fixed inset-0 opacity-[0.02]">
        <svg width="100%" height="100%">
          <defs>
            <pattern id="hex-signin" width="40" height="40" patternUnits="userSpaceOnUse">
              <path
                d="M20 0 L40 10 L40 30 L20 40 L0 30 L0 10 Z"
                fill="none"
                stroke="#ffffff"
                strokeWidth="0.5"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#hex-signin)" />
        </svg>
      </div>

      <div className="relative w-full max-w-md">
        {/* Back button */}
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-[#a0a0b8] hover:text-white text-sm mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to home
        </Link>

        {/* Card */}
        <div className="bg-[#14141e] border border-[#252538] rounded-xl p-8">
          {/* Header */}
          <div className="flex items-center gap-2 mb-2">
            <Network className="w-6 h-6 text-[#7c6bff]" />
            <span className="text-white font-semibold text-lg" style={{ fontFamily: 'Space Grotesk' }}>
              FlowDesk
            </span>
          </div>
          <h1
            className="text-2xl font-semibold text-white mb-1"
            style={{ fontFamily: 'Space Grotesk' }}
          >
            Sign In
          </h1>
          <p className="text-[#a0a0b8] text-sm mb-6">Welcome back — sign in to your account</p>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-[#a0a0b8] text-sm">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="bg-[#0a0a0f] border-[#252538] text-white placeholder:text-[#6b6b80] h-11 focus:border-[#7c6bff] focus:ring-[#7c6bff20]"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-[#a0a0b8] text-sm">
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  className="bg-[#0a0a0f] border-[#252538] text-white placeholder:text-[#6b6b80] h-11 pr-10 focus:border-[#7c6bff] focus:ring-[#7c6bff20]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6b6b80] hover:text-[#a0a0b8] transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-[#ff5a5a15] border border-[#ff5a5a40] rounded-lg px-4 py-3">
                <p className="text-[#ff5a5a] text-sm">{error}</p>
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-[#7c6bff] hover:bg-[#9b8fff] text-white h-11 font-medium transition-all"
            >
              {loading ? <Spinner className="w-4 h-4 mr-2" /> : null}
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-[#252538]" />
            <span className="text-[#6b6b80] text-xs">or</span>
            <div className="flex-1 h-px bg-[#252538]" />
          </div>

          {/* Sign up link */}
          <p className="text-center text-[#a0a0b8] text-sm">
            Don't have an account?{' '}
            <Link to="/signup" className="text-[#7c6bff] hover:text-[#9b8fff] font-medium transition-colors">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
