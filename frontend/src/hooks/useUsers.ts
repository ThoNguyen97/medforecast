import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  usersService,
  type UserCreatePayload,
  type UserUpdatePayload,
} from '../services/usersService';
import { useAuthStore } from '../store/authStore';

export function useUsers() {
  const { user, isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['users', 'list'],
    queryFn: () => usersService.list(),
    enabled: isAuthenticated && user?.role === 'Administrator',
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserCreatePayload) => usersService.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users', 'list'] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UserUpdatePayload }) =>
      usersService.update(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users', 'list'] }),
  });
}

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => usersService.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users', 'list'] }),
  });
}

export function useToggleUserActive() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      usersService.toggleActive(id, is_active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users', 'list'] }),
  });
}
