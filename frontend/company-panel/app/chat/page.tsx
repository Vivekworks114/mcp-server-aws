'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { chatAPI, companyAPI, CompanyInfo } from '@/lib/api';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'agent';
  timestamp: Date;
}

// Format AI response text with proper styling
const formatMessageText = (text: string): React.ReactNode => {
  if (!text) return text;
  
  // Split text by numbered list pattern: "number. " 
  // Match pattern: space(s) + number + period + space(s)
  const splitRegex = /(\s+)(\d+)\.\s+/g;
  const parts: Array<{ type: 'text' | 'list'; content: string; num?: string }> = [];
  const splits: Array<{ index: number; num: string; fullMatch: string }> = [];
  
  // Find all split points
  let match;
  while ((match = splitRegex.exec(text)) !== null) {
    splits.push({
      index: match.index,
      num: match[2],
      fullMatch: match[0]
    });
  }
  
  // If no numbered lists found, return as regular formatted text
  if (splits.length === 0) {
    return (
      <div className="text-gray-700 leading-relaxed whitespace-pre-wrap">
        {formatInlineText(text)}
      </div>
    );
  }
  
  // Process text segments
  let lastIndex = 0;
  for (let i = 0; i < splits.length; i++) {
    const split = splits[i];
    
    // Text before this list item
    if (split.index > lastIndex) {
      const beforeText = text.substring(lastIndex, split.index).trim();
      if (beforeText) {
        parts.push({ type: 'text', content: beforeText });
      }
    }
    
    // Content of this list item (until next item or end)
    const itemStart = split.index + split.fullMatch.length;
    const itemEnd = i < splits.length - 1 ? splits[i + 1].index : text.length;
    const itemContent = text.substring(itemStart, itemEnd).trim();
    
    if (itemContent) {
      parts.push({ type: 'list', content: itemContent, num: split.num });
    }
    
    lastIndex = itemEnd;
  }
  
  // Remaining text after last list item
  if (lastIndex < text.length) {
    const remaining = text.substring(lastIndex).trim();
    if (remaining) {
      parts.push({ type: 'text', content: remaining });
    }
  }
  
  // Render formatted parts
  return (
    <div className="space-y-2.5">
      {parts.map((part, idx) => {
        if (part.type === 'list' && part.num) {
          return (
            <div key={idx} className="flex gap-3 items-start">
              <span className="font-semibold text-gray-700 flex-shrink-0 min-w-[28px] pt-0.5">{part.num}.</span>
              <div className="flex-1 text-gray-700 leading-relaxed">
                {formatInlineText(part.content)}
              </div>
            </div>
          );
        } else {
          return (
            <p key={idx} className="text-gray-700 leading-relaxed">
              {formatInlineText(part.content)}
            </p>
          );
        }
      })}
    </div>
  );
};

// Format inline text (bold, line breaks)
const formatInlineText = (text: string): React.ReactNode => {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  
  // Match bold text (**text**)
  const boldRegex = /\*\*(.+?)\*\*/g;
  let match;
  
  while ((match = boldRegex.exec(text)) !== null) {
    // Add text before the match
    if (match.index > lastIndex) {
      const beforeText = text.substring(lastIndex, match.index);
      if (beforeText) {
        parts.push(formatLineBreaks(beforeText));
      }
    }
    
    // Add bold text
    parts.push(
      <strong key={match.index} className="font-semibold">
        {match[1]}
      </strong>
    );
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    const remainingText = text.substring(lastIndex);
    if (remainingText) {
      parts.push(formatLineBreaks(remainingText));
    }
  }
  
  return parts.length > 0 ? <>{parts}</> : formatLineBreaks(text);
};

// Format line breaks
const formatLineBreaks = (text: string): React.ReactNode => {
  const lines = text.split('\n');
  if (lines.length === 1) return text;
  
  return (
    <>
      {lines.map((line, idx) => (
        <React.Fragment key={idx}>
          {line}
          {idx < lines.length - 1 && <br />}
        </React.Fragment>
      ))}
    </>
  );
};

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }
    loadCompanyInfo();
  }, [router]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadCompanyInfo = async () => {
    try {
      const info = await companyAPI.getInfo();
      setCompanyInfo(info);
    } catch (error) {
      console.error('Failed to load company info:', error);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: input,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatAPI.sendMessage(input, sessionId || undefined);
      
      if (!sessionId && response.session_id) {
        setSessionId(response.session_id);
      }

      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.response,
        sender: 'agent',
        timestamp: new Date(response.timestamp),
      };

      setMessages((prev) => [...prev, agentMessage]);
    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: error.response?.data?.detail || 'Failed to get response from agent',
        sender: 'agent',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('company_id');
    localStorage.removeItem('role');
    router.push('/login');
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold">
                {companyInfo?.name || 'Company'} - Chat Assistant
              </h1>
            </div>
            <div className="flex items-center">
              <button
                onClick={handleLogout}
                className="text-gray-700 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 mt-20">
              <p className="text-lg">Start a conversation with your company's AI assistant</p>
              <p className="text-sm mt-2">Ask questions about your company's products, services, or policies</p>
            </div>
          )}

          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.sender === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`max-w-xs lg:max-w-2xl xl:max-w-3xl px-5 py-4 rounded-lg ${
                    message.sender === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-gray-900 shadow-md border border-gray-100'
                  }`}
                >
                  {message.sender === 'agent' ? (
                    <div className="text-sm leading-relaxed">
                      {formatMessageText(message.text)}
                    </div>
                  ) : (
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.text}</p>
                  )}
                  <p
                    className={`text-xs mt-3 ${
                      message.sender === 'user' ? 'text-blue-100' : 'text-gray-500'
                    }`}
                  >
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white text-gray-900 shadow px-4 py-2 rounded-lg">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>

      <div className="bg-white border-t px-4 py-4">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSend} className="flex space-x-4">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
