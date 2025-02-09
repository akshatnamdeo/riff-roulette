import Link from 'next/link';
import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';

const Navigation = () => {
    return (
        <AppBar position="static" sx={{ backgroundColor: '#1a1a1a', height: '5vh' }}>
            <Toolbar>
                <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    RiffRoulette
                </Typography>
                <Box>
                    <Button color="inherit" component={Link} href="/">
                        Home
                    </Button>
                    <Button color="inherit" component={Link} href="/playground">
                        Playground
                    </Button>
                </Box>
            </Toolbar>
        </AppBar>
    );
};

export default Navigation;
