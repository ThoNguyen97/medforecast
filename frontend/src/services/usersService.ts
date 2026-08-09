import api from './api';
import type { User } from '../types/auth';

export type UserRole = 'Administrator' | 'Pharmacist' | 'Inventory_Manager';

export interface UserCreatePayload {
  username: string;
  email: string;
  full_name?: string | null;
  role: UserRole;
  password: string;
}

export interface UserUpdatePayload {
  email?: string;
  full_name?: string | null;
  role?: UserRole;
  is_active?: boolean;
}

export const usersService = {
  async list(): Promise<User[]> {
    const res = await api.get<User[]>('/users/');
    return res.data;
  },

  async create(payload: UserCreatePayload): Promise<User> {
    const res = await api.post<User>('/users/', payload);
    return res.data;
  },

  async update(id: number, payload: UserUpdatePayload): Promise<User> {
    const res = await api.put<User>(`/users/${id}`, payload);
    return res.data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/users/${id}`);
  },

  async toggleActive(id: number, is_active: boolean): Promise<User> {
    const res = await api.put<User>(`/users/${id}`, { is_active });
    return res.data;
  },
};
