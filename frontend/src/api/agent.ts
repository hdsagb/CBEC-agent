import { http } from '@/api/http'

export interface AgentTool {
  name: string
  description: string
  parameters: Record<string, unknown>
}

export interface ChatSession {
  id: number
  user_id: number
  title: string
}

export interface ChatMessage {
  id: number
  session_id: number
  role: string // user | assistant | tool
  content: string
  tool_calls_json: string
}

/** 工具执行结果（与后端 app/schemas/chat.py 的 ToolResult 对应） */
export interface ToolResult {
  name: string
  result: Record<string, unknown>
}

export function fetchAgentTools() {
  return http.get<AgentTool[]>('/agent/tools')
}

export function createAgentSession() {
  return http.post<ChatSession>('/agent/sessions')
}

export function fetchAgentSessions() {
  return http.get<ChatSession[]>('/agent/sessions')
}

export function fetchAgentMessages(sessionId: number) {
  return http.get<ChatMessage[]>(`/agent/sessions/${sessionId}/messages`)
}

export function sendAgentMessage(sessionId: number | null, content: string) {
  return http.post<ChatMessage>('/agent/chat', { session_id: sessionId, content })
}