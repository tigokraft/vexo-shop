import { prisma } from '@/lib/prisma';
import { requireAdminUser } from '@/lib/admin-guard';
import { ok, badRequest, conflict, serverError } from '@/lib/http';
import { z } from 'zod';
import { slugify } from '@/lib/slug';
import { audit } from '@/lib/audit';

export const runtime = 'nodejs';

const imageSchema = z.object({
  url: z.string().url(),
  alt: z.string().max(300).optional(),
  position: z.number().int().min(0).optional(),
});
const createSchema = z.object({
  title: z.string().min(2).max(200),
  slug: z.string().min(2).max(200).optional(),
  description: z.string().max(5000).optional(),
  brandId: z.string().uuid().nullable().optional(),
  status: z.enum(['DRAFT','PUBLISHED','ARCHIVED']).optional(),
  categoryIds: z.array(z.string().uuid()).optional(),
  images: z.array(imageSchema).optional(),
  skuPrefix: z.string().max(40).optional(),
});

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const page = Math.max(1, Number(searchParams.get('page') ?? '1'));
  const pageSize = Math.min(100, Math.max(1, Number(searchParams.get('pageSize') ?? '20')));
  const q = (searchParams.get('q') ?? '').trim();
  const status = searchParams.get('status') as 'DRAFT'|'PUBLISHED'|'ARCHIVED'|null;
  const brandId = searchParams.get('brandId');
  const categoryId = searchParams.get('categoryId');

  const where: any = {};
  if (q) where.OR = [{ title: { contains: q, mode: 'insensitive' } }, { slug: { contains: q, mode: 'insensitive' } }];
  if (status) where.status = status;
  if (brandId) where.brandId = brandId;
  if (categoryId) where.categories = { some: { categoryId } };

  const [total, items] = await Promise.all([
    prisma.product.count({ where }),
    prisma.product.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * pageSize,
      take: pageSize,
      include: { brand: true, categories: { include: { category: true } }, variants: true },
    }),
  ]);

  return ok({ items, page, pageSize, total, hasMore: page * pageSize < total });
}

export async function POST(req: Request) {
  const { user, error } = await requireAdminUser();
  if (error) return error;

  const body = await req.json().catch(() => null);
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const { title, slug, description, brandId, status, categoryIds, images, skuPrefix } = parsed.data;
  const normalizedSlug = slug ? slugify(slug) : slugify(title);

  try {
    // 1) Fast path: if exists, just return it (200)
    const existing = await prisma.product.findUnique({ where: { slug: normalizedSlug } });
    if (existing) return ok(existing); // <- no 409s in dev

    // 2) Create new
    const created = await prisma.product.create({
      data: {
        title,
        slug: normalizedSlug,
        description,
        brandId: brandId ?? null,
        status: status ?? 'DRAFT',
        skuPrefix: skuPrefix ?? title.split(/\s+/).map(s => s[0]).join('').toUpperCase(),
        categories: categoryIds?.length ? { create: categoryIds.map(id => ({ categoryId: id })) } : undefined,
        images: images?.length ? { create: images.map((img, i) => ({ ...img, position: img.position ?? i })) } : undefined,
      },
    });

    await audit({ actorUserId: user.id, action: 'product.create', entityType: 'Product', entityId: created.id, after: created });
    return ok(created, { status: 201 });
  } catch (e: any) {
    // Fallback in case of a rare race: if it still hit P2002, return the existing row
    if (e?.code === 'P2002') {
      const row = await prisma.product.findUnique({ where: { slug: normalizedSlug } });
      if (row) return ok(row);
    }
    return serverError('Failed to create product', e);
  }
}
