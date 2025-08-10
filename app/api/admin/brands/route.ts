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
  website: z.string().url().optional(),
  logoUrl: z.string().url().optional(),
});

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const page = Math.max(1, Number(searchParams.get('page') ?? '1'));
  const pageSize = Math.min(100, Math.max(1, Number(searchParams.get('pageSize') ?? '20')));
  const q = (searchParams.get('q') ?? '').trim();

  const where = q
    ? { OR: [{ name: { contains: q, mode: 'insensitive' } }, { slug: { contains: q, mode: 'insensitive' } }] }
    : {};

  const [total, items] = await Promise.all([
    prisma.brand.count({ where }),
    prisma.brand.findMany({
      where,
      orderBy: { createdAt: 'desc' },
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

  const { name, slug: incomingSlug, description, website, logoUrl } = parsed.data;
  const slug = incomingSlug ? slugify(incomingSlug) : slugify(name);

  try {
    const created = await prisma.brand.create({
      data: { name, slug, description, website, logoUrl },
    });
    await audit({
      actorUserId: user.id,
      action: 'brand.create',
      entityType: 'Brand',
      entityId: created.id,
      after: created,
    });
    return NextResponse.json(created, { status: 201 });
  } catch (e: any) {
    if (e?.code === 'P2002') return conflict('Name or slug already exists');
    return serverError('Failed to create brand', e);
  }
}
