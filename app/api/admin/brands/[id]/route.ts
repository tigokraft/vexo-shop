import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, conflict, serverError } from '@/lib/http';
import { requireAdminUser } from '@/lib/admin-guard';
import { z } from 'zod';
import { slugify } from '@/lib/slug';
import { audit } from '@/lib/audit';

export const runtime = 'nodejs';

const updateSchema = z.object({
  name: z.string().min(2).max(120).optional(),
  slug: z.string().min(2).max(140).optional(),
  description: z.string().max(2000).nullable().optional(),
  website: z.string().url().nullable().optional(),
  logoUrl: z.string().url().nullable().optional(),
});

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const brand = await prisma.brand.findUnique({ where: { id: params.id } });
  if (!brand) return notFound('Brand not found');
  return ok(brand);
}

export async function PUT(req: Request, { params }: { params: { id: string } }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;

  const body = await req.json().catch(() => null);
  const parsed = updateSchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const existing = await prisma.brand.findUnique({ where: { id: params.id } });
  if (!existing) return notFound('Brand not found');

  const data: any = { ...parsed.data };
  if (data.slug) data.slug = slugify(data.slug);

  try {
    const updated = await prisma.brand.update({ where: { id: params.id }, data });
    await audit({
      actorUserId: user.id,
      action: 'brand.update',
      entityType: 'Brand',
      entityId: updated.id,
      before: existing,
      after: updated,
    });
    return ok(updated);
  } catch (e: any) {
    if (e?.code === 'P2002') return conflict('Name or slug already exists');
    return serverError('Failed to update brand', e);
  }
}

export async function DELETE(_: Request, { params }: { params: { id: string } }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;

  const existing = await prisma.brand.findUnique({ where: { id: params.id } });
  if (!existing) return notFound('Brand not found');

  try {
    const deleted = await prisma.brand.delete({ where: { id: params.id } });
    await audit({
      actorUserId: user.id,
      action: 'brand.delete',
      entityType: 'Brand',
      entityId: deleted.id,
      before: existing,
    });
    return ok({ ok: true });
  } catch (e: any) {
    return serverError('Failed to delete brand', e);
  }
}
