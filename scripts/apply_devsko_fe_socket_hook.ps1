$hookPath = 'C:\Users\soumy\Desktop\CODES\DevskoFE\src\hooks\useInterviewAgentSocket.ts'
$hookContent = @'
import { useCallback, useEffect, useRef, useState } from "react";
import { io, Socket } from "socket.io-client";

const INTERVIEW_SOCKET_BASE_URL =
    process.env.NEXT_PUBLIC_INTERVIEW_SOCKET_BASE_URL ||
    process.env.NEXT_PUBLIC_SOCKET_BASE_URL ||
    "http://localhost:8000";

type QuestionHandler = (payload: any) => void;
type CompleteHandler = (payload: any) => void;
type ErrorHandler = (error: Error) => void;

interface UseInterviewAgentSocketProps {
    sessionId: string | null;
    enabled: boolean;
    onQuestion: QuestionHandler;
    onComplete?: CompleteHandler;
    onConnectError?: ErrorHandler;
}

const buildSessionPayload = (sessionId: string) => ({
    session_id: sessionId,
    session_slug: sessionId,
    session_token: sessionId,
    userassessmentsessionuuid: sessionId,
});

export default function useInterviewAgentSocket({
    sessionId,
    enabled,
    onQuestion,
    onComplete,
    onConnectError,
}: UseInterviewAgentSocketProps) {
    const socketRef = useRef<Socket | null>(null);
    const sessionRef = useRef<string | null>(sessionId);
    const questionHandlerRef = useRef(onQuestion);
    const completeHandlerRef = useRef(onComplete);
    const connectErrorHandlerRef = useRef(onConnectError);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        sessionRef.current = sessionId;
    }, [sessionId]);

    useEffect(() => {
        questionHandlerRef.current = onQuestion;
    }, [onQuestion]);

    useEffect(() => {
        completeHandlerRef.current = onComplete;
    }, [onComplete]);

    useEffect(() => {
        connectErrorHandlerRef.current = onConnectError;
    }, [onConnectError]);

    useEffect(() => {
        if (!enabled || !sessionId) return;

        const socket = io(INTERVIEW_SOCKET_BASE_URL, {
            reconnectionAttempts: 5,
            transports: ["websocket", "polling"],
        });

        socketRef.current = socket;

        socket.on("connect", () => {
            setIsConnected(true);
            const currentSession = sessionRef.current;
            if (!currentSession) return;
            socket.emit("join_interview", buildSessionPayload(currentSession));
        });

        socket.on("disconnect", () => {
            setIsConnected(false);
        });

        socket.on("next_question", (payload: any) => {
            questionHandlerRef.current?.(payload);
        });

        socket.on("interview_completed", (payload: any) => {
            completeHandlerRef.current?.(payload);
        });

        socket.on("connect_error", (error: Error) => {
            setIsConnected(false);
            connectErrorHandlerRef.current?.(error);
        });

        return () => {
            socket.disconnect();
            socketRef.current = null;
            setIsConnected(false);
        };
    }, [enabled, sessionId]);

    const sendAnswer = useCallback((text: string) => {
        const currentSession = sessionRef.current;
        const socket = socketRef.current;
        if (!currentSession || !socket || !socket.connected) {
            return false;
        }

        socket.emit("user_answer", {
            ...buildSessionPayload(currentSession),
            text,
        });
        return true;
    }, []);

    const rejoin = useCallback(() => {
        const currentSession = sessionRef.current;
        const socket = socketRef.current;
        if (!currentSession || !socket) {
            return false;
        }

        if (socket.connected) {
            socket.emit("join_interview", buildSessionPayload(currentSession));
            return true;
        }

        socket.connect();
        return true;
    }, []);

    return {
        isConnected,
        sendAnswer,
        rejoin,
    };
}
'@
Set-Content -Path $hookPath -Value $hookContent

$interviewPath = 'C:\Users\soumy\Desktop\CODES\DevskoFE\src\components\Refector\Organisms\InterviewScreen\interview2.tsx'
$content = Get-Content -Path $interviewPath -Raw

$content = $content.Replace(
    'import useSnackbar from "@/hooks/useSnackbar";',
    "import useInterviewAgentSocket from `"@/hooks/useInterviewAgentSocket`";`r`nimport useSnackbar from `"@/hooks/useSnackbar`";"
)
$content = $content.Replace(
    'import { getData, postData, putData } from "@/lib/api";',
    'import { getData, interviewAgentBaseApiUrl, postData, putData } from "@/lib/api";'
)
$content = $content.Replace(
    "import {`r`n    createUserAssessmentPostEP,`r`n    nextQuestionGetEP,`r`n    submitQuestionPostEP,`r`n} from `"@/lib/endPoints`";",
    "import {`r`n    createUserAssessmentPostEP,`r`n} from `"@/lib/endPoints`";"
)

$content = $content.Replace(
    '        const config = useAppSelector(selectConfig);',
@'
        const config = useAppSelector(selectConfig);
        const [socketEnabled, setSocketEnabled] = useState(false);
        const pendingSocketModeRef = useRef<string | undefined>(undefined);

        const applySocketQuestion = (questionData: any) => {
            if (timeOutRef.current) clearTimeout(timeOutRef.current);
            if (captureTimeoutRef.current) clearTimeout(captureTimeoutRef.current);

            const questiontext = isReadingType(questionData?.questiontypeid)
                ? questionData?.metadata?.instructions
                      ?.replace(/<\/?p>|<br\s*\/?>/gi, "")
                      ?.trim()
                : questionData?.questiontext;

            if (pendingSocketModeRef.current === "resume") {
                dispatch(setInterviewStage(InterviewStage.TEST_STARTED));
            }

            skipTextSpeakingTimeRef.current = 0;
            dataToConvert({
                data: questiontext,
                callback: () => {
                    dispatch(setNextQuestion(questionData));
                    if (firstQuestion) setFirstQuestion(false);
                },
            });
            pendingSocketModeRef.current = undefined;
            setFailedApiStates(null);
        };

        const {
            sendAnswer: sendSocketAnswer,
            rejoin: rejoinInterviewSocket,
        } = useInterviewAgentSocket({
            sessionId:
                ids.userassessmentsessionuuid || userAssessmentSessionUUID || null,
            enabled: socketEnabled,
            onQuestion: applySocketQuestion,
            onComplete: (payload) => {
                completeInterview({
                    type: "complete",
                    textToSpeak: payload?.message,
                });
            },
            onConnectError: (error) => {
                logger.error({
                    msg: "Interview socket connection failed",
                    data: error,
                    component: "Interview2.tsx",
                    uuid: uuid,
                    isCustom: Boolean(uuid),
                });
                setFailedApiStates({
                    open: true,
                    handler: callNextQuestion,
                    args: [pendingSocketModeRef.current],
                });
                dispatch(setButtonResponse(false));
            },
        });
'@
)

$oldCallNext = @'
        const callNextQuestion: CallNextQuestionHandler = async (
            type?: string
        ) => {
            if (type === "resume")
                dispatch(setInterviewStage(InterviewStage.RESUMED));
            const res2 = await getData({
                url: nextQuestionGetEP(
                    ids.userassessmentsessionuuid || userAssessmentSessionUUID,
                    ids.userassessmentsessionid || userAssessmentSessionId
                ),
                isCustom: Boolean(uuid),
                uuid: uuid,
            });
            if (res2.type === "success") {
                const { status, data } = res2.response;
                if (status == 204) {
                    completeInterview({ type: "complete" });
                    return;
                }
                setFailedApiStates(null);
                switch (data?.code) {
                    case InterviewCodes.ANALYSIS_IN_PROGRESS:
                        if (skipTextSpeakingTimeRef.current === 0) {
                            skipTextSpeakingTimeRef.current += 1;
                            dataToConvert({
                                code: InterviewCodes.ANALYSIS_IN_PROGRESS,
                                callback: () => {
                                    speak(waitForQuestion, SpeechType.NORMAL);
                                },
                            });
                        }
                        timeOutRef.current = setTimeout(() => {
                            skipTextSpeakingTimeRef.current += 1;
                            callNextQuestion(type);
                        }, config[DynamicConfigKeys.INTERVIEW_ANALYSIS_RETRY_INTERVAL]);
                        break;
                    case InterviewCodes.SKIP_LIMIT_EXCEEDED:
                        return completeInterview({
                            type: "complete",
                            code: InterviewCodes.SKIP_LIMIT_EXCEEDED,
                            timer: 10000,
                        });
                    case InterviewCodes.PERFORMANCE_BELOW_THRESHOLD:
                        return completeInterview({
                            type: "complete",
                            code: InterviewCodes.PERFORMANCE_BELOW_THRESHOLD,
                            timer: 10000,
                        });
                    case InterviewCodes.COMPLETION:
                        return completeInterview({
                            type: "complete",
                            code: InterviewCodes.COMPLETION,
                        });
                    default:
                        if (timeOutRef.current)
                            clearTimeout(timeOutRef.current);
                        if (captureTimeoutRef.current)
                            clearTimeout(captureTimeoutRef.current);

                        const _data = data.data;
                        const questiontext = isReadingType(
                            _data?.questiontypeid
                        )
                            ? _data?.metadata?.instructions
                                  ?.replace(/<\/?p>|<br\s*\/?>/gi, "")
                                  ?.trim()
                            : _data.questiontext;

                        if (type === "resume") {
                            dispatch(
                                setInterviewStage(InterviewStage.TEST_STARTED)
                            );
                        }
                        skipTextSpeakingTimeRef.current = 0;
                        dataToConvert({
                            data: questiontext,
                            callback: () => {
                                dispatch(setNextQuestion(_data));
                                if (firstQuestion) setFirstQuestion(false);
                            },
                        });
                        logger.info({
                            msg: "Recieved next question data",
                            data: _data,
                            component: "Interview2.tsx",
                            uuid: uuid,
                            isCustom: Boolean(uuid),
                        });
                        return true;
                }
            } else if (res2.type === "network_error") {
                setFailedApiStates({
                    open: true,
                    handler: callNextQuestion,
                    args: [type],
                });
                dispatch(setButtonResponse(false));
                return false;
            } else {
                showSnackbar({
                    message: res2.message?.message || "An error occurred",
                    autohide: 5000,
                    severity: "error",
                });
                completeInterview({ type: "complete" });
            }
        };
'@
$newCallNext = @'
        const callNextQuestion: CallNextQuestionHandler = async (
            type?: string
        ) => {
            pendingSocketModeRef.current = type;
            if (type === "resume") {
                dispatch(setInterviewStage(InterviewStage.RESUMED));
            }

            if (!socketEnabled) {
                setSocketEnabled(true);
                return true;
            }

            const joined = rejoinInterviewSocket();
            if (!joined) {
                setFailedApiStates({
                    open: true,
                    handler: callNextQuestion,
                    args: [type],
                });
                dispatch(setButtonResponse(false));
                return false;
            }

            return true;
        };
'@
$content = $content.Replace($oldCallNext, $newCallNext)

$content = $content.Replace(
    '                    isCustom: Boolean(uuid),`r`n                    uuid: uuid,`r`n                });',
    '                    baseUrl: interviewAgentBaseApiUrl,`r`n                    isCustom: Boolean(uuid),`r`n                    uuid: uuid,`r`n                });'
)
$content = $content.Replace(
    '                        payload: {},`r`n                        isCustom: Boolean(uuid),',
    '                        payload: {},`r`n                        baseUrl: interviewAgentBaseApiUrl,`r`n                        isCustom: Boolean(uuid),'
)
$content = $content.Replace(
    '                        isCustom: Boolean(uuid),`r`n                        uuid: uuid,`r`n                    });',
    '                        baseUrl: interviewAgentBaseApiUrl,`r`n                        isCustom: Boolean(uuid),`r`n                        uuid: uuid,`r`n                    });'
)

$content = $content.Replace(
@'
                        getFirstQuestion();
                        setIds({
                            userassessmentsessionuuid:
                                userAssessmentSessionUUID,
                            userassessmentsessionid: userAssessmentSessionId,
                        });
'@,
@'
                        const nextSessionIds = {
                            userassessmentsessionuuid:
                                userAssessmentSessionUUID,
                            userassessmentsessionid: userAssessmentSessionId,
                        };
                        setIds(nextSessionIds);
                        pendingSocketModeRef.current = "resume";
                        setSocketEnabled(true);
'@
)

$content = $content.Replace(
@'
                const getFirstQuestion = async () => {
                    if (!firstQuestion) return;
                    const res = await getData({
                        url: nextQuestionGetEP(
                            ids.userassessmentsessionuuid,
                            ids.userassessmentsessionid
                        ),
                        isCustom: Boolean(uuid),
                        uuid: uuid,
                    });
                    if (res.type == "success") {
                        if (res?.response?.status === 204) {
                            completeInterview({ type: "complete" });
                            return;
                        }
                        if (res?.response?.data.code === 420) {
                            callNextQuestion();
                        }
                        const ques = res?.response?.data.data;
                        const questiontext = isReadingType(ques?.questiontypeid)
                            ? ques?.metadata?.instructions
                                  ?.replace(/<\/?p>|<br\s*\/?>/gi, "")
                                  ?.trim()
                            : ques.questiontext;
                        dataToConvert({
                            data: questiontext,
                            callback: () => {
                                dispatch(setNextQuestion(ques));
                                setFirstQuestion(false);
                            },
                        });
                    } else if (res.type === "network_error") {
                        setFailedApiStates({
                            open: true,
                            handler: callNextQuestion,
                            args: [],
                        });
                        dispatch(setButtonResponse(false));
                        return;
                    } else {
                        completeInterview({ type: "complete" });
                        return;
                    }
                };
                getFirstQuestion();
'@,
@'
                if (firstQuestion) {
                    pendingSocketModeRef.current = undefined;
                    setSocketEnabled(true);
                }
'@
)

$oldSubmit = @'
            const res1 = await postData({
                url: submitQuestionPostEP(),
                payload: payload,
                isCustom: Boolean(uuid),
                uuid: uuid,
            });

            if (res1.type == "success") {
                setQuestionResponseTimeComplete(false);
                callNextQuestion();
                setFailedApiStates(null);
                logger.info({
                    msg: "Question submission success",
                    data: res1.response,
                    component: "Interview2.tsx",
                    uuid: uuid,
                    isCustom: Boolean(uuid),
                });
            } else if (res1.type === "error" && res1.message?.code === 409) {
                showSnackbar({
                    message: "Response Already Submitted",
                    autohide: 5000,
                    severity: "warning",
                });
                setQuestionResponseTimeComplete(false);
                callNextQuestion();
                setFailedApiStates(null);
            } else if (res1.type === "network_error") {
                setFailedApiStates({
                    open: true,
                    args: [type, callBack, payload],
                    handler: handleSubmitQuestion,
                });
                dispatch(setButtonResponse(false));
                return false;
            } else {
                showSnackbar({
                    message: res1.message?.message || "An error occurred",
                    autohide: 5000,
                    severity: "error",
                });
                completeInterview({ type: "complete" });
            }
            callBack?.();
            return true;
'@
$newSubmit = @'
            const answerParts = [
                payload.response.verbal,
                payload.response.text,
                payload.response.code,
                payload.response.query,
            ].filter(Boolean);
            const answerText =
                type === "skip"
                    ? "Skipped"
                    : type === "timedout" && answerParts.length === 0
                      ? "Time Out"
                      : answerParts.join("\n\n");

            const sent = sendSocketAnswer(answerText);
            if (!sent) {
                setFailedApiStates({
                    open: true,
                    args: [type, callBack, payload],
                    handler: handleSubmitQuestion,
                });
                dispatch(setButtonResponse(false));
                return false;
            }

            setQuestionResponseTimeComplete(false);
            setFailedApiStates(null);
            logger.info({
                msg: "Question submission sent over socket",
                data: { type, answerText },
                component: "Interview2.tsx",
                uuid: uuid,
                isCustom: Boolean(uuid),
            });
            callBack?.();
            return true;
'@
$content = $content.Replace($oldSubmit, $newSubmit)

Set-Content -Path $interviewPath -Value $content
