import { NextResponse } from 'next/server';

export function ok(data: any, init?: number | ResponseInit) {
  return NextResponse.json(data, typeof init === 'number' ? { status: init } : init);
}
export function badRequest(message = 'Bad Request', details?: any) {
  return NextResponse.json({ error: message, details }, { status: 400 });
}
export function unauthorized(message = 'Unauthorized') {
  return NextResponse.json({ error: message }, { status: 401 });
}
export function forbidden(message = 'Forbidden') {
  return NextResponse.json({ error: message }, { status: 403 });
}
export function notFound(message = 'Not Found') {
  return NextResponse.json({ error: message }, { status: 404 });
}
export function conflict(message = 'Conflict') {
  return NextResponse.json({ error: message }, { status: 409 });
}
export function serverError(message = 'Server Error', details?: any) {
  console.error('[500]', message, details);
  return NextResponse.json({ error: message }, { status: 500 });
}
