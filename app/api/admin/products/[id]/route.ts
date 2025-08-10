import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, conflict, serverError } from '@/lib/http';
import { requireAdminUser } from '@/lib/admin-guard';
import { z } from 'zod';
import { slugify } from '@/lib/slug';
import { audit } from '@/lib/audit';

export const runtime = 'nodejs';

const imageSchema = z.object({
  url: z.string().url(),
  alt: z.string().max(300).nullable().optional(),
  position: z.number().int().min(0).optional(),
});
const updateSchema = z.object({
  title: z.string().min(2).max(200).optional(),
  slug: z.string().min(2).max(200).optional(),
  description: z.string().max(5000).nullable().optional(),
  brandId: z.string().uuid().nullable().optional(),
  status: z.enum(['DRAFT','PUBLISHED','ARCHIVED']).optional(),
  skuPrefix: z.string().max(40).nullable().optional(),
  categoryIds: z.array(z.string().uuid()).optional(), // replaces full set when provided
  images: z.array(imageSchema).optional(),            // replaces full set when provided
});

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const prod = await prisma.product.findUnique({
    where: { id },
    include: {
      brand: true,
      categories: { include: { category: true } },
      images: true,
      options: { include: { values: true } },
      variants: { include: { variantOptions: true, stockLevels: true } },
    },
  });
  if (!prod) return notFound('Product not found');
  return ok(prod);
}

export async function PUT(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;

  const body = await req.json().catch(() => null);
  const parsed = updateSchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());
  const { id } = await ctx.params;

  const existing = await prisma.product.findUnique({ where: { id }, include: { categories: true, images: true } });
  if (!existing) return notFound('Product not found');

  const data: any = { ...parsed.data };
  if (data.slug) data.slug = slugify(data.slug);

  try {
    const updated = await prisma.$transaction(async (tx) => {
      if (data.categoryIds) {
        await tx.productCategory.deleteMany({ where: { productId: id } });
        await tx.productCategory.createMany({ data: data.categoryIds.map((cid: string) => ({ productId: id, categoryId: cid })) });
        delete data.categoryIds;
      }
      if (data.images) {
        await tx.productImage.deleteMany({ where: { productId: id } });
        await tx.productImage.createMany({
          data: data.images.map((img: any, i: number) => ({
            productId: id,
            url: img.url,
            alt: img.alt ?? null,
            position: img.position ?? i,
          })),
        });
        delete data.images;
      }
      return tx.product.update({ where: { id }, data });
    });

    await audit({ actorUserId: user.id, action: 'product.update', entityType: 'Product', entityId: updated.id, before: existing, after: updated });
    return ok(updated);
  } catch (e: any) {
    if (e?.code === 'P2002') return conflict('Slug already exists');
    return serverError('Failed to update product', e);
  }
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;
  const { id } = await ctx.params;

  const existing = await prisma.product.findUnique({ where: { id } });
  if (!existing) return notFound('Product not found');

  try {
    const deleted = await prisma.product.delete({ where: { id } });
    await audit({ actorUserId: user.id, action: 'product.delete', entityType: 'Product', entityId: deleted.id, before: existing });
    return ok({ ok: true });
  } catch (e: any) {
    return serverError('Failed to delete product', e);
  }
}
