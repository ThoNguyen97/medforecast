import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Login from '../Login';
import { useAuth } from '../../hooks/useAuth';

// Mock useAuth to avoid real network calls
vi.mock('../../hooks/useAuth');

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
}

describe('Login page', () => {
  const mockLogin = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      login: mockLogin,
      logout: vi.fn(),
      user: null,
      isAuthenticated: false,
      refreshToken: vi.fn(),
      checkAndRefreshToken: vi.fn(),
    });
  });

  it('renders username and password inputs', () => {
    renderLogin();
    expect(screen.getByLabelText(/tên đăng nhập/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/mật khẩu/i)).toBeInTheDocument();
  });

  it('renders submit button', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /đăng nhập/i })).toBeInTheDocument();
  });

  it('shows app name', () => {
    renderLogin();
    expect(screen.getByText('MedForecast AI')).toBeInTheDocument();
  });

  it('shows validation error when fields are empty', async () => {
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /đăng nhập/i }));
    await waitFor(() => {
      expect(screen.getByText(/vui lòng nhập/i)).toBeInTheDocument();
    });
  });

  it('calls login with credentials on submit', async () => {
    mockLogin.mockResolvedValueOnce({ success: true });
    renderLogin();

    fireEvent.change(screen.getByLabelText(/tên đăng nhập/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/mật khẩu/i), {
      target: { value: 'password123' },
    });
    fireEvent.submit(screen.getByRole('button', { name: /đăng nhập/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        username: 'admin',
        password: 'password123',
      });
    });
  });

  it('navigates to dashboard on successful login', async () => {
    mockLogin.mockResolvedValueOnce({ success: true });
    renderLogin();

    fireEvent.change(screen.getByLabelText(/tên đăng nhập/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/mật khẩu/i), {
      target: { value: 'password123' },
    });
    fireEvent.submit(screen.getByRole('button', { name: /đăng nhập/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalled();
    });
  });

  it('shows error message on failed login', async () => {
    mockLogin.mockResolvedValueOnce({ success: false, error: 'Invalid credentials' });
    renderLogin();

    fireEvent.change(screen.getByLabelText(/tên đăng nhập/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByLabelText(/mật khẩu/i), {
      target: { value: 'wrong' },
    });
    fireEvent.submit(screen.getByRole('button', { name: /đăng nhập/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
    });
  });

  it('toggles password visibility', () => {
    renderLogin();
    const passwordInput = screen.getByLabelText(/mật khẩu/i) as HTMLInputElement;
    expect(passwordInput.type).toBe('password');

    // Find the toggle button (tabIndex=-1)
    const toggleBtn = passwordInput.parentElement!.querySelector('button[tabindex="-1"]')!;
    fireEvent.click(toggleBtn);
    expect(passwordInput.type).toBe('text');

    fireEvent.click(toggleBtn);
    expect(passwordInput.type).toBe('password');
  });
});
