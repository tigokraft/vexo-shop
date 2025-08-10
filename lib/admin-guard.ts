import { getCurrentUser } from '@/lib/auth';
import { forbidden, unauthorized } from '@/lib/http';

export async function requireAdminUser() {
  const user = await getCurrentUser();
  if (!user) return { error: unauthorized() as const };
  if (user.role !== 'ADMIN') return { error: forbidden() as const };
  return { user };
}
