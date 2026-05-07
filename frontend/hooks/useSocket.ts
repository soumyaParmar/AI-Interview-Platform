import { useEffect, useState, useRef, useCallback } from 'react';
import io, { Socket } from 'socket.io-client';
import { SOCKET_URL } from '../lib/api';

export const useSocket = (sessionSlug: string | null, enabled: boolean = true) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<{role: string, content: string}[]>([]);
  const [status, setStatus] = useState<string>('Initializing');
  const [agentState, setAgentState] = useState<Record<string, unknown> | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const sessionRef = useRef(sessionSlug);

  useEffect(() => {
    if (typeof window !== 'undefined') {
        localStorage.debug = '*';
    }
    sessionRef.current = sessionSlug;
  }, [sessionSlug]);

  useEffect(() => {
    if (!sessionSlug || !enabled) return;
    
    console.log("Connecting to socket server...", SOCKET_URL);
    const newSocket = io(SOCKET_URL, {
        reconnectionAttempts: 5,
        transports: ['websocket', 'polling']
    });

    newSocket.on('connect', () => {
      console.log('Connected to socket server');
      setIsConnected(true);
      setMessages([]); // Clear to avoid duplicates on reconnect
      newSocket.emit('join_interview', {
        session_id: sessionSlug,
        session_token: sessionSlug,
        session_slug: sessionSlug,
      });
      setStatus('Listening');
    });

    newSocket.on('disconnect', () => {
      console.log('Disconnected from socket server');
      setIsConnected(false);
      setStatus('Disconnected');
    });

    newSocket.on('system_message', (data) => {
      setMessages(prev => [...prev, { role: 'system', content: data.content }]);
    });

    newSocket.on('transcript_update', (data) => {
      console.log('transcript_update received:', data);
      setMessages(prev => [...prev, { role: data.role, content: data.content }]);
      
      // Fallback: If agent sends a message, we should be in Listening mode
      if (data.role === 'agent') {
        console.log('Agent message received, auto-resetting status to Listening');
        setStatus('Listening');
      }
    });

    newSocket.on('status_update', (data) => {
      console.log('status_update received:', data.status);
      setStatus(data.status);
    });

    newSocket.on('agent_state', (data) => {
      console.log('agent_state received:', data);
      setAgentState(data);
    });

    newSocket.on('phase_transition', (data) => {
      setAgentState(prev => ({ ...(prev || {}), phase: data.to }));
    });

    newSocket.on('topic_transition', (data) => {
      setAgentState(prev => ({ ...(prev || {}), current_topic: data.to }));
    });

    newSocket.on('report_ready', (data) => {
      console.log("Report is ready!");
      setReport(data.report);
      setStatus('Completed');
    });

    setSocket(newSocket);

    return () => {
      console.log("Disconnecting socket...");
      newSocket.disconnect();
    };
  }, [sessionSlug, enabled]);

  const sendAnswer = useCallback((text: string) => {
    if (socket && isConnected && sessionRef.current) {
      socket.emit('user_answer', {
        session_id: sessionRef.current,
        session_token: sessionRef.current,
        session_slug: sessionRef.current,
        text
      });
    } else {
        console.warn("Cannot send answer, socket not connected.");
    }
  }, [socket, isConnected]);

  const terminateInterview = useCallback(() => {
    console.log("terminateInterview hook called", { hasSocket: !!socket, isConnected, slug: sessionRef.current });
    if (socket && isConnected && sessionRef.current) {
      socket.emit('terminate_interview', {
        session_id: sessionRef.current,
        session_token: sessionRef.current,
        session_slug: sessionRef.current
      });
    }
  }, [socket, isConnected]);

  return { socket, isConnected, messages, status, agentState, report, sendAnswer, terminateInterview };
};
