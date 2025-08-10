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
  parentId: z.string().uuid().nullable().optional(),
});

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const category = await prisma.category.findUnique({
    where: { id },
    include: { parent: true, children: true },
  });
  if (!category) return notFound('Category not found');
  return ok(category);
}

export async function PUT(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;

  const body = await req.json().catch(() => null);
  const parsed = updateSchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const { id } = await ctx.params;

  const existing = await prisma.category.findUnique({ where: { id } });
  if (!existing) return notFound('Category not found');

  const data: any = { ...parsed.data };
  if (data.slug) data.slug = slugify(data.slug);

  if (data.parentId === id) return badRequest('A category cannot be its own parent');

  try {
    const updated = await prisma.category.update({ where: { id }, data });
    await audit({
      actorUserId: user.id,
      action: 'category.update',
      entityType: 'Category',
      entityId: updated.id,
      before: existing,
      after: updated,
    });
    return ok(updated);
  } catch (e: any) {
    if (e?.code === 'P2002') return conflict('Slug already exists or name clashes among siblings');
    return serverError('Failed to update category', e);
  }
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;

  const { id } = await ctx.params;

  const existing = await prisma.category.findUnique({ where: { id } });
  if (!existing) return notFound('Category not found');

  try {
    const deleted = await prisma.category.delete({ where: { id } });
    await audit({
      actorUserId: user.id,
      action: 'category.delete',
      entityType: 'Category',
      entityId: deleted.id,
      before: existing,
    });
    return ok({ ok: true });
  } catch (e: any) {
    return serverError('Failed to delete category', e);
  }
}
