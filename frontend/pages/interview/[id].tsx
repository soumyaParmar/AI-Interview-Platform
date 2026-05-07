import { useRouter } from 'next/router';
import Head from 'next/head';
import InterviewRoom from '../../components/InterviewRoom';

export default function InterviewPage() {
    const router = useRouter();
    const { id } = router.query;

    if (!id || typeof id !== 'string') {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50 text-gray-800">
                <div className="animate-pulse">Loading Interview Room...</div>
            </div>
        );
    }

    return (
        <>
            <Head>
                <title>Interview | Devsko AI</title>
                <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
            </Head>
            
            <InterviewRoom sessionSlug={id} />
        </>
    );
}
