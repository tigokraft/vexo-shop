import { prisma } from '@/lib/prisma';

export async function audit(opts: {
  actorUserId?: string | null;
  action: string;
  entityType?: string;
  entityId?: string;
  before?: any;
  after?: any;
  ip?: string | null;
}) {
  const { actorUserId = null, action, entityType, entityId, before, after, ip = null } = opts;
  await prisma.auditLog.create({
    data: {
      actorUserId: actorUserId ?? undefined,
      action,
      entityType,
      entityId,
      before: before ? (before as any) : undefined,
      after: after ? (after as any) : undefined,
      ip: ip ?? undefined,
    },
  });
}
