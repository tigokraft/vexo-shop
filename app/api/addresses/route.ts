import { prisma } from '@/lib/prisma';
import { ok, badRequest, unauthorized } from '@/lib/http';
import { getCurrentUser } from '@/lib/auth';
import { z } from 'zod';

const AddressSchema = z.object({
  fullName: z.string().min(1).max(200),
  line1: z.string().min(1).max(200),
  line2: z.string().max(200).optional().nullable(),
  city: z.string().min(1).max(120),
  region: z.string().max(120).optional().nullable(), // state/province
  postalCode: z.string().min(2).max(32),
  country: z.string().min(2).max(2), // ISO 3166-1 alpha-2
  phone: z.string().max(40).optional().nullable(),
  company: z.string().max(200).optional().nullable(),
  label: z.string().max(64).optional().nullable(), // "home", "office"...
});

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return unauthorized('Login required');
  const addresses = await prisma.address.findMany({
    where: { userId: user.id },
    orderBy: { createdAt: 'desc' },
  });
  return ok(addresses);
}

export async function POST(req: Request) {
  const user = await getCurrentUser(); // may be null (guest)
  const json = await req.json().catch(() => ({}));
  const parsed = AddressSchema.safeParse(json);
  if (!parsed.success) return badRequest('Invalid address', parsed.error.format());

  const created = await prisma.address.create({
    data: {
      ...(user ? { user: { connect: { id: user.id } } } : {}),
      ...parsed.data,
    },
  });

  return ok(created);
}
