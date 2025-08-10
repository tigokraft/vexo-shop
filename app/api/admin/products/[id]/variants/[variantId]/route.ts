import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, conflict, serverError } from '@/lib/http';
import { requireAdminUser } from '@/lib/admin-guard';
import { z } from 'zod';
import { makeSku } from '@/lib/sku';
import { audit } from '@/lib/audit';

export const runtime = 'nodejs';

const updateSchema = z.object({
  sku: z.string().min(1).max(100).optional(),
  title: z.string().min(1).max(200).optional(),
  priceCents: z.number().int().min(0).optional(),
  compareAtCents: z.number().int().min(0).nullable().optional(),
  costCents: z.number().int().min(0).nullable().optional(),
  currency: z.string().length(3).optional(),
  trackInventory: z.boolean().optional(),
  isDefault: z.boolean().optional(),
  regenSkuFromProductPrefix: z.boolean().optional(), // helper flag
});

export async function PUT(req: Request, ctx: { params: Promise<{ variantId: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;
  const { variantId } = await ctx.params;

  const payload = await req.json().catch(() => null);
  const parsed = updateSchema.safeParse(payload);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const variant = await prisma.productVariant.findUnique({ where: { id: variantId }, include: { product: true } });
  if (!variant) return notFound('Variant not found');

  const data: any = { ...parsed.data };
  if (data.regenSkuFromProductPrefix) {
    data.sku = makeSku(variant.product.skuPrefix, [variant.title || 'VAR']);
    delete data.regenSkuFromProductPrefix;
  }

  try {
    const updated = await prisma.productVariant.update({ where: { id: variantId }, data });
    await audit({ actorUserId: user.id, action: 'variant.update', entityType: 'ProductVariant', entityId: variantId, before: variant, after: updated });
    return ok(updated);
  } catch (e: any) {
    if (e?.code === 'P2002') return conflict('SKU already exists');
    return serverError('Failed to update variant', e);
  }
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ variantId: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;
  const { variantId } = await ctx.params;

  const existing = await prisma.productVariant.findUnique({ where: { id: variantId } });
  if (!existing) return notFound('Variant not found');

  try {
    const deleted = await prisma.productVariant.delete({ where: { id: variantId } });
    await audit({ actorUserId: user.id, action: 'variant.delete', entityType: 'ProductVariant', entityId: deleted.id, before: existing });
    return ok({ ok: true });
  } catch (e: any) {
    return serverError('Failed to delete variant', e);
  }
}
