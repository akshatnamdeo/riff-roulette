import { Box, Typography } from '@mui/material';
import { useSpring, useSprings, animated } from 'react-spring';
import { useEffect } from 'react';

const Cloud = ({
    initialTransform, targetTransform, delay, size, color
}: {
    initialTransform: string;
    targetTransform: string;
    delay: number;
    size: string;
    color: string;
}) => {
    const props = useSpring({
        from: { transform: initialTransform },
        to: { transform: targetTransform },
        config: { duration: 15000 }, // Faster animation
        loop: { reverse: true },
        delay,
    });

    return (
        <animated.div
            style={{
                position: 'absolute',
                width: size,
                height: size,
                borderRadius: '50%',
                background: color,
                filter: 'blur(80px)',
                opacity: 0.8, // More visible
                ...props,
            }}
        />
    );
};

const CloudBackground = () => {
    return (
        <>
            <Cloud
                initialTransform="translate(-10%, -20%)"
                targetTransform="translate(10%, -10%)"
                delay={0}
                size="40vw"
                color="rgba(255,20,147,0.4)"
            />
            <Cloud
                initialTransform="translate(60%, 10%)"
                targetTransform="translate(70%, 20%)"
                delay={5000}
                size="50vw"
                color="rgba(0,191,255,0.4)"
            />
            <Cloud
                initialTransform="translate(20%, 70%)"
                targetTransform="translate(30%, 80%)"
                delay={10000}
                size="45vw"
                color="rgba(138,43,226,0.4)"
            />
            <Cloud
                initialTransform="translate(-20%, 50%)"
                targetTransform="translate(-10%, 60%)"
                delay={15000}
                size="35vw"
                color="rgba(75,0,130,0.4)"
            />
        </>
    );
};

const WaveVisualizer = () => {
    const numBars = 12; // Fewer bars
    const barWidth = 30; // Thicker bars
    const [springs, api] = useSprings(numBars, (i) => ({
        height: 20,
    }));

    useEffect(() => {
        const animate = () => {
            api.start((i) => ({
                from: { height: 20 },
                to: async (next) => {
                    await next({ height: 100 }); // Peak height
                    await next({ height: 20 }); // Back to base
                },
                config: { duration: 200 }, // Faster animation
                delay: i * 100, // Staggered delay for ripple effect
            }));
        };

        const interval = setInterval(animate, 1500); // Faster loop
        animate(); // Initial trigger
        return () => clearInterval(interval);
    }, [api]);

    return (
        <Box
            sx={{
                position: 'absolute',
                top: '53%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '150px', // Adjusted height
                width: '80vw',
                maxWidth: '800px',
                zIndex: 1,
            }}
        >
            {springs.map((style, i) => (
                <animated.div
                    key={i}
                    style={{
                        ...style,
                        width: `${barWidth}px`,
                        margin: '0 10px', // Spacing between bars
                        background: 'rgba(255,20,147,0.8)', // Neon pink
                        borderRadius: `${barWidth / 2}px`, // Rounded edges for bars
                    }}
                />
            ))}
        </Box>
    );
};

const Home = () => {
    return (
        <Box
            sx={{
                position: 'relative',
                width: '100%',
                height: '100vh',
                overflow: 'hidden',
                background: '#0a0a0a',
            }}
        >
            {/* Cloudy Background */}
            <Box
                sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    zIndex: 0,
                    overflow: 'hidden',
                }}
            >
                <CloudBackground />
            </Box>

            {/* Overlay with Wave Visualizer and Title */}
            <Box
                sx={{
                    position: 'relative',
                    zIndex: 1,
                    width: '100%',
                    height: '100%',
                }}
            >
                {/* Wave Visualizer behind the title */}
                <WaveVisualizer />
                {/* Overlay Title */}
                <Box
                    sx={{
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        zIndex: 2,
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        width: '100%',
                    }}
                >
                    <Typography
                        variant="h1"
                        sx={{
                            fontWeight: '900',
                            textTransform: 'lowercase',
                            color: '#fff',
                            textAlign: 'center',
                            fontSize: { xs: '3rem', md: '6rem' },
                            textShadow: '0 2px 10px rgba(0,0,0,0.5)',
                        }}
                    >
                        RiffRoulette
                    </Typography>
                </Box>
            </Box>
        </Box>
    );
};

export default Home;
