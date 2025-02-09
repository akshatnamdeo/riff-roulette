import { Box } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
import { AppProps } from 'next/app';
import Head from 'next/head';
import Navigation from '../components/global/Navigation';

const App = ({ Component, pageProps }: AppProps) => {
    return (
        <Box sx={{ position: 'relative', minHeight: '100vh' }}>
            <Head>
                <title>RiffRoulette</title>
                <link
                    href="https://fonts.googleapis.com/css2?family=Dancing+Script:wght@400..700&display=swap"
                    rel="stylesheet"
                />
                <meta name="viewport" content="initial-scale=1.0, width=device-width" />
            </Head>
            <CssBaseline />
            <Navigation />
            <Component {...pageProps} />
        </Box>
    );
};

export default App;
