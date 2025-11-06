import { randomUUID } from "crypto"
import { mkdir, writeFile } from "fs/promises"
import path from "path"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

const DEFAULT_UPLOAD_DIR = path.join(process.cwd(), "uploads")
const UPLOAD_DIR = process.env.MINDQ_UPLOAD_DIR ? path.resolve(process.env.MINDQ_UPLOAD_DIR) : DEFAULT_UPLOAD_DIR
const MAX_UPLOAD_BYTES = Number(process.env.MINDQ_MAX_UPLOAD_BYTES ?? 1024 * 1024 * 1024) // 1GB default

const sanitizeFileName = (name: string) => name.replace(/[^a-zA-Z0-9.\-_]/g, "_")

const ensureUploadDir = async () => {
  await mkdir(UPLOAD_DIR, { recursive: true })
}

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const file = formData.get("file")

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "File is required" }, { status: 400 })
  }

  if (Number.isFinite(MAX_UPLOAD_BYTES) && file.size > MAX_UPLOAD_BYTES) {
    return NextResponse.json({ error: "File exceeds maximum allowed size" }, { status: 413 })
  }

  const fileBuffer = Buffer.from(await file.arrayBuffer())
  await ensureUploadDir()

  const uniquePrefix = `${Date.now()}-${randomUUID()}`
  const safeName = sanitizeFileName(file.name)
  const storedFileName = `${uniquePrefix}-${safeName}`
  const storedPath = path.join(UPLOAD_DIR, storedFileName)

  await writeFile(storedPath, fileBuffer)

  return NextResponse.json({
    originalName: file.name,
    storedFileName,
    path: storedPath,
    size: file.size,
  })
}
