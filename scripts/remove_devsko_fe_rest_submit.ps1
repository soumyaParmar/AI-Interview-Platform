$path = 'C:\Users\soumy\Desktop\CODES\DevskoFE\src\components\Refector\Organisms\InterviewScreen\interview2.tsx'
$content = Get-Content -Path $path -Raw

$oldBlock = @'
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

$newBlock = @'
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

$content = $content.Replace($oldBlock, $newBlock)
Set-Content -Path $path -Value $content
