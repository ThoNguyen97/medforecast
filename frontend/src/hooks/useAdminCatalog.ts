import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  adminCatalogService,
  type DiseaseItem,
  type RegionItem,
} from '../services/adminCatalogService';
import { useAuthStore } from '../store/authStore';

const ADMIN_ONLY = (role?: string) => role === 'Administrator';

// ── Diseases ────────────────────────────────────────────────────────────
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

// ── Regions ─────────────────────────────────────────────────────────────
export function useAdminRegions() {
  const { user, isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['admin', 'regions'],
    queryFn: () => adminCatalogService.listRegions(),
    enabled: isAuthenticated && ADMIN_ONLY(user?.role),
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useCreateRegion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: RegionItem) => adminCatalogService.createRegion(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'regions'] }),
  });
}

export function useDeleteRegion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => adminCatalogService.deleteRegion(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'regions'] }),
  });
}

// ── Safety rate ─────────────────────────────────────────────────────────
export function useSafetyRate() {
  const { user, isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['admin', 'safety-rate'],
    queryFn: () => adminCatalogService.getSafetyRate(),
    enabled: isAuthenticated && ADMIN_ONLY(user?.role),
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateSafetyRate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rate: number) => adminCatalogService.updateSafetyRate(rate),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'safety-rate'] }),
  });
}
