$path = 'C:\Users\soumy\Desktop\CODES\DevskoFE\src\components\Refector\Organisms\InterviewScreen\interview2.tsx'
$content = Get-Content -Path $path -Raw

$content = $content.Replace(
    "import {`r`n    createUserAssessmentPostEP,`r`n    submitQuestionPostEP,`r`n} from `"@/lib/endPoints`";",
    "import {`r`n    createUserAssessmentPostEP,`r`n} from `"@/lib/endPoints`";"
)

$oldSocketBlock = @'
        const config = useAppSelector(selectConfig);
        const socketRef = useRef<Socket | null>(null);

        const getInterviewSocket = () => {
            if (!socketRef.current) {
                socketRef.current = io(interviewSocketBaseUrl, {
                    transports: ["websocket"],
                });
            }
            return socketRef.current;
        };

        const applyNextQuestion = (questionData: any, type?: string) => {
            if (timeOutRef.current) clearTimeout(timeOutRef.current);
            if (captureTimeoutRef.current) clearTimeout(captureTimeoutRef.current);

            const questiontext = isReadingType(questionData?.questiontypeid)
                ? questionData?.metadata?.instructions
                      ?.replace(/<\/?p>|<br\s*\/?>/gi, "")
                      ?.trim()
                : questionData?.questiontext;

            if (type === "resume") {
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
            logger.info({
                msg: "Recieved next question data",
                data: questionData,
                component: "Interview2.tsx",
                uuid: uuid,
                isCustom: Boolean(uuid),
            });
            return true;
        };

        const requestNextQuestionViaSocket = async (type?: string) => {
            if (type === "resume") {
                dispatch(setInterviewStage(InterviewStage.RESUMED));
            }

            try {
                const socket = getInterviewSocket();
                const response = await new Promise<any>((resolve, reject) => {
                    socket.timeout(20000).emit(
                        "request_next_question",
                        {
                            session_id:
                                ids.userassessmentsessionuuid ||
                                userAssessmentSessionUUID,
                            session_slug:
                                ids.userassessmentsessionuuid ||
                                userAssessmentSessionUUID,
                            session_token:
                                ids.userassessmentsessionuuid ||
                                userAssessmentSessionUUID,
                            userassessmentsessionuuid:
                                ids.userassessmentsessionuuid ||
                                userAssessmentSessionUUID,
                            userassessmentsessionid:
                                ids.userassessmentsessionid ||
                                userAssessmentSessionId,
                        },
                        (err: Error | null, payload: any) => {
                            if (err) {
                                reject(err);
                                return;
                            }
                            resolve(payload);
                        }
                    );
                });

                setFailedApiStates(null);
                switch (response?.code) {
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
                            requestNextQuestionViaSocket(type);
                        }, config[DynamicConfigKeys.INTERVIEW_ANALYSIS_RETRY_INTERVAL]);
                        return false;
                    case InterviewCodes.SKIP_LIMIT_EXCEEDED:
                        completeInterview({
                            type: "complete",
                            code: InterviewCodes.SKIP_LIMIT_EXCEEDED,
                            timer: 10000,
                        });
                        return false;
                    case InterviewCodes.PERFORMANCE_BELOW_THRESHOLD:
                        completeInterview({
                            type: "complete",
                            code: InterviewCodes.PERFORMANCE_BELOW_THRESHOLD,
                            timer: 10000,
                        });
                        return false;
                    case InterviewCodes.COMPLETION:
                    case 423:
                        completeInterview({
                            type: "complete",
                            code: InterviewCodes.COMPLETION,
                        });
                        return false;
                    default:
                        if (!response?.success || !response?.data) {
                            throw new Error(
                                response?.message || "Unable to fetch next question"
                            );
                        }
                        return applyNextQuestion(response.data, type);
                }
            } catch (error: any) {
                logger.error({
                    msg: "Next question socket request failed",
                    data: error,
                    component: "Interview2.tsx",
                    uuid: uuid,
                    isCustom: Boolean(uuid),
                });
                setFailedApiStates({
                    open: true,
                    handler: callNextQuestion,
                    args: [type],
                });
                dispatch(setButtonResponse(false));
                return false;
            }
        };

        useEffect(() => {
            return () => {
                socketRef.current?.disconnect();
                socketRef.current = null;
            };
        }, []);
'@

$newSocketBlock = @'
        const config = useAppSelector(selectConfig);
        const socketRef = useRef<Socket | null>(null);
        const firstQuestionRef = useRef(firstQuestion);
        const pendingJoinModeRef = useRef<string | undefined>(undefined);
        const pendingSessionRef = useRef<{
            userassessmentsessionuuid: string;
            userassessmentsessionid: number;
        } | null>(null);

        useEffect(() => {
            firstQuestionRef.current = firstQuestion;
        }, [firstQuestion]);

        const applyNextQuestion = (questionData: any, type?: string) => {
            if (timeOutRef.current) clearTimeout(timeOutRef.current);
            if (captureTimeoutRef.current) clearTimeout(captureTimeoutRef.current);

            const questiontext = isReadingType(questionData?.questiontypeid)
                ? questionData?.metadata?.instructions
                      ?.replace(/<\/?p>|<br\s*\/?>/gi, "")
                      ?.trim()
                : questionData?.questiontext;

            if (type === "resume") {
                dispatch(setInterviewStage(InterviewStage.TEST_STARTED));
            }
            skipTextSpeakingTimeRef.current = 0;
            dataToConvert({
                data: questiontext,
                callback: () => {
                    dispatch(setNextQuestion(questionData));
                    if (firstQuestionRef.current) {
                        firstQuestionRef.current = false;
                        setFirstQuestion(false);
                    }
                },
            });
            logger.info({
                msg: "Recieved next question data",
                data: questionData,
                component: "Interview2.tsx",
                uuid: uuid,
                isCustom: Boolean(uuid),
            });
            return true;
        };

        const buildSessionPayload = (
            sessionOverride?: {
                userassessmentsessionuuid: string;
                userassessmentsessionid: number;
            }
        ) => {
            const activeSession =
                sessionOverride || {
                    userassessmentsessionuuid:
                        ids.userassessmentsessionuuid ||
                        userAssessmentSessionUUID,
                    userassessmentsessionid:
                        ids.userassessmentsessionid || userAssessmentSessionId,
                };

            return {
                session_id: activeSession.userassessmentsessionuuid,
                session_slug: activeSession.userassessmentsessionuuid,
                session_token: activeSession.userassessmentsessionuuid,
                userassessmentsessionuuid:
                    activeSession.userassessmentsessionuuid,
                userassessmentsessionid:
                    activeSession.userassessmentsessionid,
            };
        };

        const getInterviewSocket = () => {
            if (!socketRef.current) {
                const socket = io(interviewSocketBaseUrl, {
                    transports: ["websocket"],
                    autoConnect: false,
                });

                socket.on("connect", () => {
                    if (!pendingSessionRef.current) return;
                    socket.emit(
                        "join_interview",
                        buildSessionPayload(pendingSessionRef.current)
                    );
                });

                socket.on("next_question", (payload: any) => {
                    setFailedApiStates(null);
                    applyNextQuestion(payload, pendingJoinModeRef.current);
                    pendingJoinModeRef.current = undefined;
                });

                socket.on("interview_completed", (payload: any) => {
                    completeInterview({
                        type: "complete",
                        textToSpeak: payload?.message,
                    });
                });

                socket.on("connect_error", (error: Error) => {
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
                        args: [pendingJoinModeRef.current],
                    });
                    dispatch(setButtonResponse(false));
                });

                socketRef.current = socket;
            }
            return socketRef.current;
        };

        const joinInterviewSocket = (
            type?: string,
            sessionOverride?: {
                userassessmentsessionuuid: string;
                userassessmentsessionid: number;
            }
        ) => {
            const sessionPayload = buildSessionPayload(sessionOverride);
            if (!sessionPayload.userassessmentsessionuuid) {
                return false;
            }

            if (type === "resume") {
                dispatch(setInterviewStage(InterviewStage.RESUMED));
            }

            pendingJoinModeRef.current = type;
            pendingSessionRef.current = {
                userassessmentsessionuuid:
                    sessionPayload.userassessmentsessionuuid,
                userassessmentsessionid:
                    sessionPayload.userassessmentsessionid,
            };

            const socket = getInterviewSocket();
            if (socket.connected) {
                socket.emit("join_interview", sessionPayload);
            } else {
                socket.connect();
            }
            return true;
        };

        useEffect(() => {
            return () => {
                socketRef.current?.disconnect();
                socketRef.current = null;
            };
        }, []);
'@

$content = $content.Replace($oldSocketBlock, $newSocketBlock)

$content = $content.Replace(
@'
        const callNextQuestion: CallNextQuestionHandler = async (
            type?: string
        ) => {
            return requestNextQuestionViaSocket(type);
        };
'@,
@'
        const callNextQuestion: CallNextQuestionHandler = async (
            type?: string
        ) => {
            return joinInterviewSocket(type);
        };
'@
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
                        joinInterviewSocket("resume", nextSessionIds);
'@
)

$content = $content.Replace(
@'
                dispatch(setInterviewStage(InterviewStage.TEST_STARTED));
                                const getFirstQuestion = async () => {
                    if (!firstQuestion) return;
                    await callNextQuestion();
                };
                getFirstQuestion();
'@,
@'
                dispatch(setInterviewStage(InterviewStage.TEST_STARTED));
                if (firstQuestion) {
                    callNextQuestion();
                }
'@
)

$oldSubmitBlock = @'
            const res1 = await postData({
                url: submitQuestionPostEP(),
                baseUrl: interviewAgentBaseApiUrl,
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

$newSubmitBlock = @'
            const socket = getInterviewSocket();
            const sessionPayload = buildSessionPayload();
            const answerParts = [
                payload.response?.verbal,
                payload.response?.text,
                payload.response?.code,
                payload.response?.query,
            ].filter(Boolean);
            const answerText =
                type === "skip"
                    ? "Skipped"
                    : type === "timedout" && answerParts.length === 0
                      ? "Time Out"
                      : answerParts.join("\n\n");

            if (!socket.connected || !sessionPayload.userassessmentsessionuuid) {
                setFailedApiStates({
                    open: true,
                    args: [type, callBack, payload],
                    handler: handleSubmitQuestion,
                });
                dispatch(setButtonResponse(false));
                return false;
            }

            socket.emit("user_answer", {
                ...sessionPayload,
                text: answerText,
            });

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

$content = $content.Replace($oldSubmitBlock, $newSubmitBlock)

Set-Content -Path $path -Value $content
