import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

const DEFAULT_BACKEND_BASE = "http://localhost:9000"

const getBackendBase = () => {
  const configured = process.env.MINDQ_API_BASE_URL?.trim()
  return configured && configured.length > 0 ? configured.replace(/\/$/, "") : DEFAULT_BACKEND_BASE
}

const buildTargetUrl = (segments: string[], search: string) => {
  const base = getBackendBase()
  const path = segments.join("/")
  const url = `${base}/${path}${search ? `?${search}` : ""}`
  return url
}

const forwardHeaders = (request: NextRequest) => {
  const headers = new Headers(request.headers)
  headers.delete("host")
  headers.delete("content-length")
  headers.delete("connection")
  headers.delete("content-encoding")
  return headers
}

const proxy = async (request: NextRequest, segments: string[]) => {
  const targetUrl = buildTargetUrl(segments, request.nextUrl.searchParams.toString())
  const method = request.method.toUpperCase()
  const inboundHeaders = forwardHeaders(request)
  let body: BodyInit | undefined

  if (!["GET", "HEAD"].includes(method)) {
    const contentType = inboundHeaders.get("content-type") ?? ""
    if (contentType.includes("application/json")) {
      const json = await request.text()
      body = json
    } else if (contentType.includes("application/x-www-form-urlencoded")) {
      const formData = await request.formData()
      const params = new URLSearchParams()
      formData.forEach((value, key) => {
        if (typeof value === "string") {
          params.append(key, value)
        }
      })
      body = params
    } else {
      const buffer = await request.arrayBuffer()
      body = Buffer.from(buffer)
    }
  }

  const response = await fetch(targetUrl, {
    method,
    headers: inboundHeaders,
    body,
    redirect: "manual",
    cache: "no-store",
  })

  const responseHeaders = new Headers(response.headers)
  responseHeaders.delete("content-encoding")
  responseHeaders.delete("transfer-encoding")
  responseHeaders.set("Access-Control-Allow-Origin", "*")

  const responseBuffer = Buffer.from(await response.arrayBuffer())

  return new NextResponse(responseBuffer, {
    status: response.status,
    headers: responseHeaders,
  })
}

export async function GET(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  const params = await context.params
  return proxy(request, params.segments)
}

export async function POST(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  const params = await context.params
  return proxy(request, params.segments)
}

export async function HEAD(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  const params = await context.params
  return proxy(request, params.segments)
}

export async function PUT(request: NextRequest, context: { params: { segments: string[] } }) {
  return proxy(request, context.params.segments)
}

export async function DELETE(request: NextRequest, context: { params: { segments: string[] } }) {
  return proxy(request, context.params.segments)
}

export async function PATCH(request: NextRequest, context: { params: { segments: string[] } }) {
  return proxy(request, context.params.segments)
}
