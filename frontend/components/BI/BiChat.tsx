"use client"

import React, { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  Send, 
  X, 
  Brain, 
  Loader2, 
  Sparkles,
  MessageSquare,
  BarChart3,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  User,
  Bot
} from "lucide-react";
import { api } from "@/lib/api";

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isTyping?: boolean;
}

interface BiChatProps {
  runId: string;
  onClose: () => void;
  currentMetrics: any;
}

export function BiChat({ runId, onClose, currentMetrics }: BiChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'assistant',
      content: 'مرحباً! أنا مساعدك الذكي لتحليل البيانات. يمكنني مساعدتك في:\n\n• تحليل الاتجاهات والأنماط\n• إنشاء رسوم بيانية جديدة\n• شرح البيانات الحالية\n• اقتراح تحسينات\n\nما الذي تريد معرفته عن بياناتك؟',
      timestamp: new Date()
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  };

  const addMessage = (content: string, type: 'user' | 'assistant') => {
    const newMessage: Message = {
      id: Date.now().toString(),
      type,
      content,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const addTypingMessage = () => {
    const typingMessage: Message = {
      id: 'typing',
      type: 'assistant',
      content: '',
      timestamp: new Date(),
      isTyping: true
    };
    setMessages(prev => [...prev, typingMessage]);
  };

  const removeTypingMessage = () => {
    setMessages(prev => prev.filter(msg => msg.id !== 'typing'));
  };

  const generateContextualPrompt = (userQuestion: string) => {
    if (!currentMetrics) return userQuestion;

    let context = `البيانات الحالية المتاحة:\n`;
    
    if (currentMetrics.orders_daily?.length > 0) {
      const totalOrders = currentMetrics.orders_daily.reduce((sum: number, item: any) => sum + (item.count || item.val || 0), 0);
      context += `• إجمالي الطلبات: ${totalOrders}\n`;
      context += `• عدد الأيام: ${currentMetrics.orders_daily.length}\n`;
    }

    if (currentMetrics.cod_rate_daily?.length > 0) {
      const avgRate = currentMetrics.cod_rate_daily.reduce((sum: number, item: any) => sum + (item.rate || item.val || 0), 0) / currentMetrics.cod_rate_daily.length;
      context += `• متوسط معدل الدفع عند التسليم: ${(avgRate * 100).toFixed(1)}%\n`;
    }

    if (currentMetrics.avg_cod_amount_destination?.length > 0) {
      context += `• عدد الوجهات: ${currentMetrics.avg_cod_amount_destination.length}\n`;
    }

    context += `\nسؤال المستخدم: ${userQuestion}`;
    return context;
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    addMessage(userMessage, 'user');
    setIsLoading(true);
    addTypingMessage();

    try {
      // Try BI LLM first
      const contextualPrompt = generateContextualPrompt(userMessage);
      
      let response;
      try {
        response = await api.biPlan(runId, contextualPrompt, { llm_enabled: true });
        
        if (response.plan) {
          removeTypingMessage();
          
          let assistantResponse = '';
          
          if (response.plan.explain_ar && typeof response.plan.explain_ar === 'string') {
            assistantResponse = response.plan.explain_ar;
          } else if (response.plan.metric || response.plan.chart_type) {
            assistantResponse = `تم تحليل طلبك بنجاح! `;
            
            if (response.plan.metric) {
              assistantResponse += `\n\n📊 المقياس المقترح: ${response.plan.metric}`;
            }
            
            if (response.plan.chart_type) {
              assistantResponse += `\n📈 نوع الرسم البياني: ${response.plan.chart_type}`;
            }
            
            if (response.plan.sql) {
              assistantResponse += `\n\n💻 استعلام SQL:\n\`\`\`sql\n${response.plan.sql}\n\`\`\``;
            }
            
            assistantResponse += `\n\n✨ يمكنني إنشاء هذا التحليل فوراً إذا كنت تريد!`;
          } else {
            assistantResponse = 'تم معالجة طلبك، لكن لم أتمكن من إنشاء تحليل محدد. هل يمكنك توضيح المطلوب أكثر؟';
          }
          
          addMessage(assistantResponse, 'assistant');
        } else {
          throw new Error('No plan generated');
        }
      } catch (biError) {
        // Fallback to SLA chat
        try {
          const slaResponse = await fetch('/api/mindq/v1/sla/chat', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              run_id: runId,
              question: userMessage,
              top_k: 5
            })
          });

          if (slaResponse.ok) {
            const slaData = await slaResponse.json();
            removeTypingMessage();
            
            let assistantResponse = slaData.answer || 'عذراً، لم أتمكن من معالجة طلبك.';
            
            if (slaData.references && slaData.references.length > 0) {
              assistantResponse += '\n\n📚 المراجع:';
              slaData.references.forEach((ref: any, index: number) => {
                assistantResponse += `\n${index + 1}. ${ref.title} (Score: ${ref.score.toFixed(2)})`;
              });
            }
            
            addMessage(assistantResponse, 'assistant');
          } else {
            throw new Error('SLA chat failed');
          }
        } catch (slaError) {
          // Final fallback with smart responses based on keywords
          removeTypingMessage();
          
          const smartResponse = generateSmartResponse(userMessage, currentMetrics);
          addMessage(smartResponse, 'assistant');
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      removeTypingMessage();
      addMessage('عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة مرة أخرى.', 'assistant');
    } finally {
      setIsLoading(false);
    }
  };

  const generateSmartResponse = (question: string, metrics: any) => {
    const lowerQuestion = question.toLowerCase();
    
    if (lowerQuestion.includes('طلبات') || lowerQuestion.includes('أوردر') || lowerQuestion.includes('معدل') || lowerQuestion.includes('متوسط')) {
      if (metrics?.orders_daily?.length > 0) {
        const totalOrders = metrics.orders_daily.reduce((sum: number, item: any) => sum + (item.count || item.val || 0), 0);
        const avgPerDay = Math.round(totalOrders / metrics.orders_daily.length);
        const daysCount = metrics.orders_daily.length;
        
        return `📊 **تحليل الطلبات الحالي:**

🔢 **إجمالي الطلبات:** ${totalOrders.toLocaleString()} طلب
📅 **متوسط الطلبات اليومية:** ${avgPerDay.toLocaleString()} طلب/يوم  
📈 **عدد الأيام المحللة:** ${daysCount} يوم
📊 **معدل الطلبات:** ${avgPerDay} طلب في اليوم الواحد

✨ **رؤى إضافية:**
• البيانات تتضمن ${totalOrders.toLocaleString()} طلب إجمالي
• المعدل اليومي يبلغ ${avgPerDay} طلب
• البيانات تغطي فترة ${daysCount} يوم

هل تريد تحليل أكثر تفصيلاً؟`;
      }
    }

    if (lowerQuestion.includes('cod') || lowerQuestion.includes('دفع') || lowerQuestion.includes('استلام')) {
      if (metrics?.cod_rate_daily?.length > 0) {
        const avgCodRate = metrics.cod_rate_daily.reduce((sum: number, item: any) => sum + (item.rate || item.val || 0), 0) / metrics.cod_rate_daily.length;
        return `💰 **تحليل طرق الدفع:**

📊 متوسط معدل الدفع عند الاستلام: ${(avgCodRate * 100).toFixed(1)}%
📈 عدد الأيام المحللة: ${metrics.cod_rate_daily.length} يوم

${avgCodRate > 0.5 ? '⚠️ معدل COD مرتفع - قد يشير إلى تفضيل العملاء للدفع النقدي' : '✅ معدل COD منخفض - اعتماد جيد على الدفع المسبق'}`;
      }
    }

    if (lowerQuestion.includes('وجهة') || lowerQuestion.includes('destination') || lowerQuestion.includes('مكان')) {
      if (metrics?.avg_cod_amount_destination?.length > 0) {
        return `🌍 **تحليل الوجهات:**

📍 عدد الوجهات المختلفة: ${metrics.avg_cod_amount_destination.length}
🎯 توزيع متنوع للطلبات على مختلف المناطق

هل تريد تحليل وجهة معينة؟`;
      }
    }

    if (lowerQuestion.includes('اتجاه') || lowerQuestion.includes('trend') || lowerQuestion.includes('نمو')) {
      return `📈 **تحليل الاتجاهات:**

بناءً على البيانات الحالية، يمكننا ملاحظة:
• تطور الطلبات عبر الزمن
• أنماط الطلب اليومية  
• اتجاهات السوق

هل تريد تحليل فترة معينة؟`;
    }

    // Default response with data summary
    if (metrics?.orders_daily?.length > 0) {
      const totalOrders = metrics.orders_daily.reduce((sum: number, item: any) => sum + (item.count || item.val || 0), 0);
      return `🤖 **مساعدك الذكي جاهز!**

💡 البيانات المتاحة حالياً:
• ${totalOrders.toLocaleString()} طلب إجمالي
• ${metrics.orders_daily.length} يوم من البيانات
• معلومات تفصيلية عن الوجهات وطرق الدفع

🔍 **يمكنني مساعدتك في:**
• تحليل الطلبات والاتجاهات
• معلومات عن طرق الدفع  
• تحليل الوجهات والمناطق
• إحصائيات مخصصة

ما الذي تريد معرفته تحديداً؟`;
    }

    return `🤖 مرحباً! أنا هنا لمساعدتك في تحليل البيانات.

💭 **اسأل عن:**
• عدد الطلبات ومعدلاتها
• طرق الدفع والـ COD  
• الوجهات والمناطق
• الاتجاهات والأنماط

🔮 اكتب سؤالك وسأعطيك تحليل مفصل!`;
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const suggestedQuestions = [
    "حلل اتجاهات الطلبات هذا الشهر",
    "ما هي أفضل الوجهات من ناحية الأرباح؟",
    "أنشئ رسم بياني لمعدلات الدفع عند التسليم",
    "قارن الأداء بين الأسابيع الماضية"
  ];

  const handleSuggestedQuestion = (question: string) => {
    setInputMessage(question);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-b from-card/50 to-muted/20">
      {/* Header */}
      <div className="border-b border-border p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <Brain className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold">المساعد الذكي</h3>
              <p className="text-xs text-muted-foreground">متصل • جاهز للمساعدة</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full p-4" ref={scrollAreaRef}>
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg p-3 ${
                    message.type === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted'
                  }`}
                >
                  {message.isTyping ? (
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm">يكتب...</span>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center gap-2 mb-1">
                        {message.type === 'user' ? (
                          <User className="h-4 w-4" />
                        ) : (
                          <Bot className="h-4 w-4" />
                        )}
                        <span className="text-xs opacity-70">
                          {message.timestamp.toLocaleTimeString('ar-SA', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })}
                        </span>
                      </div>
                      <div className="text-sm whitespace-pre-wrap">
                        {message.content}
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Suggested Questions */}
      {messages.length <= 1 && (
        <div className="border-t border-border p-4">
          <p className="text-xs font-medium text-muted-foreground mb-2">أسئلة مقترحة:</p>
          <div className="space-y-2">
            {suggestedQuestions.map((question, index) => (
              <Button
                key={index}
                variant="ghost"
                size="sm"
                className="justify-start text-right w-full h-auto p-2 text-xs"
                onClick={() => handleSuggestedQuestion(question)}
              >
                <Sparkles className="h-3 w-3 ml-2 flex-shrink-0" />
                {question}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-border p-4">
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            placeholder="اكتب سؤالك هنا..."
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
            className="text-right"
          />
          <Button 
            onClick={handleSendMessage} 
            disabled={!inputMessage.trim() || isLoading}
            size="sm"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2 text-center">
          اضغط Enter للإرسال • Shift+Enter للسطر الجديد
        </p>
      </div>
    </div>
  );
}