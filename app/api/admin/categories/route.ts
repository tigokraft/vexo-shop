import { prisma } from '@/lib/prisma';
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { ok, badRequest, conflict, serverError } from '@/lib/http';
import { requireAdminUser } from '@/lib/admin-guard';
import { slugify } from '@/lib/slug';
import { audit } from '@/lib/audit';

export const runtime = 'nodejs';

const createSchema = z.object({
  name: z.string().min(2).max(120),
  slug: z.string().min(2).max(140).optional(),
  description: z.string().max(2000).optional(),
  parentId: z.string().uuid().nullable().optional(),
});

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const page = Math.max(1, Number(searchParams.get('page') ?? '1'));
  const pageSize = Math.min(100, Math.max(1, Number(searchParams.get('pageSize') ?? '20')));
  const q = (searchParams.get('q') ?? '').trim();
  const parentId = searchParams.get('parentId');

  const where: any = {};
  if (q) where.OR = [{ name: { contains: q, mode: 'insensitive' } }, { slug: { contains: q, mode: 'insensitive' } }];
  if (parentId === 'root') where.parentId = null;
  else if (parentId) where.parentId = parentId;

  const [total, items] = await Promise.all([
    prisma.category.count({ where }),
    prisma.category.findMany({
      where,
      orderBy: [{ parentId: 'asc' }, { createdAt: 'desc' }],
      skip: (page - 1) * pageSize,
      take: pageSize,
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

  const { name, slug: incomingSlug, description, parentId } = parsed.data;
  const slug = incomingSlug ? slugify(incomingSlug) : slugify(name);

  try {
    const created = await prisma.category.create({
      data: { name, slug, description, parentId: parentId ?? null },
    });
    await audit({
      actorUserId: user.id,
      action: 'category.create',
      entityType: 'Category',
      entityId: created.id,
      after: created,
    });
    return NextResponse.json(created, { status: 201 });
  } catch (e: any) {
    if (e?.code === 'P2002') return conflict('Slug must be unique (also unique among siblings by name).');
    return serverError('Failed to create category', e);
  }
}
