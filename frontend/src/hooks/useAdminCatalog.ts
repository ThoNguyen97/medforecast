import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  adminCatalogService,
  type DiseaseGroupItem,
  type DiseaseItem,
} from '../services/adminCatalogService';
import { useAuthStore } from '../store/authStore';

const ADMIN_ONLY = (role?: string) => role === 'Administrator';

// ── Danh mục bệnh ────────────────────────────────────────────────────────────
export function useAdminDiseases() {
  const { user, isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['admin', 'diseases'],
    queryFn: () => adminCatalogService.listDiseases(),
    enabled: isAuthenticated && ADMIN_ONLY(user?.role),
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useCreateDisease() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: DiseaseItem) => adminCatalogService.createDisease(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'diseases'] }),
  });
}

export function useUpdateDisease() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, payload }: { key: string; payload: DiseaseItem }) =>
      adminCatalogService.updateDisease(key, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'diseases'] }),
  });
}

export function useDeleteDisease() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => adminCatalogService.deleteDisease(key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'diseases'] }),
  });
}

// ── Nhóm bệnh ──────────────────────────────────────────────────────
export function useAdminDiseaseGroups() {
  const { user, isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['admin', 'disease-groups'],
    queryFn: () => adminCatalogService.listDiseaseGroups(),
    enabled: isAuthenticated && ADMIN_ONLY(user?.role),
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useCreateDiseaseGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: DiseaseGroupItem) => adminCatalogService.createDiseaseGroup(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'disease-groups'] }),
  });
}

export function useUpdateDiseaseGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, payload }: { key: string; payload: DiseaseGroupItem }) =>
      adminCatalogService.updateDiseaseGroup(key, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'disease-groups'] }),
  });
}

export function useDeleteDiseaseGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => adminCatalogService.deleteDiseaseGroup(key),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'disease-groups'] }),
  });
}

