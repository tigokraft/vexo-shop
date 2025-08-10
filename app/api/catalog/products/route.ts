import { prisma } from '@/lib/prisma';
import { ok, badRequest } from '@/lib/http';

export const runtime = 'nodejs';

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const page = Math.max(1, Number(searchParams.get('page') ?? '1'));
  const pageSize = Math.min(100, Math.max(1, Number(searchParams.get('pageSize') ?? '24')));

  const q = (searchParams.get('q') ?? '').trim();
  const brand = (searchParams.get('brand') ?? '').trim();
  const category = (searchParams.get('category') ?? '').trim(); // category slug
  const status = 'PUBLISHED'; // public only
  const sort = (searchParams.get('sort') ?? 'newest') as 'newest' | 'title_asc' | 'title_desc';

  // (Optional) simple bounds for price in cents (filters by variant price)
  const minPrice = searchParams.get('minPrice') ? Number(searchParams.get('minPrice')) : undefined;
  const maxPrice = searchParams.get('maxPrice') ? Number(searchParams.get('maxPrice')) : undefined;
  if ((minPrice !== undefined && Number.isNaN(minPrice)) || (maxPrice !== undefined && Number.isNaN(maxPrice))) {
    return badRequest('minPrice/maxPrice must be numbers');
  }

  // Resolve category slug -> id (if provided)
  let categoryId: string | undefined;
  if (category) {
    const cat = await prisma.category.findUnique({ where: { slug: category } });
    if (!cat) return ok({ items: [], page, pageSize, total: 0, hasMore: false });
    categoryId = cat.id;
  }

  const where: any = {
    status,
  };
  if (q) where.OR = [{ title: { contains: q, mode: 'insensitive' } }, { slug: { contains: q, mode: 'insensitive' } }, { description: { contains: q, mode: 'insensitive' } }];
  if (brand) where.brand = { is: { slug: brand } };
  if (categoryId) where.categories = { some: { categoryId } };
  if (minPrice !== undefined || maxPrice !== undefined) {
    where.variants = {
      some: {
        ...(minPrice !== undefined ? { priceCents: { gte: minPrice } } : {}),
        ...(maxPrice !== undefined ? { priceCents: { lte: maxPrice } } : {}),
      },
    };
  }

  let orderBy: any = { createdAt: 'desc' };
  if (sort === 'title_asc') orderBy = { title: 'asc' };
  if (sort === 'title_desc') orderBy = { title: 'desc' };
  // NOTE: price sorting needs a denormalized minPriceCents on Product; we’ll add later.

  const [total, items] = await Promise.all([
    prisma.product.count({ where }),
    prisma.product.findMany({
      where,
      orderBy,
      skip: (page - 1) * pageSize,
      take: pageSize,
      include: {
        brand: true,
        images: { orderBy: { position: 'asc' }, take: 1 }, // cover image
        variants: {
          orderBy: { priceCents: 'asc' }, // so first is the cheapest
          select: { id: true, sku: true, priceCents: true, currency: true, isDefault: true },
        },
      },
    }),
  ]);

  // Shape: minimal; client gets cover image and minPrice
  const shaped = items.map(p => {
    const minPrice = p.variants[0]?.priceCents ?? null;
    const currency = p.variants[0]?.currency ?? 'EUR';
    return {
      id: p.id,
      title: p.title,
      slug: p.slug,
      brand: p.brand ? { id: p.brand.id, name: p.brand.name, slug: p.brand.slug } : null,
      coverImage: p.images[0]?.url ?? null,
      minPriceCents: minPrice,
      currency,
      createdAt: p.createdAt,
    };
  });

  return ok({ items: shaped, page, pageSize, total, hasMore: page * pageSize < total }, { headers: { 'Cache-Control': 'public, s-maxage=30' } });
}
