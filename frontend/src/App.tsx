import React, { useState, useEffect } from 'react';
import { 
  Container, 
  Box, 
  FormControl, 
  InputLabel, 
  Select, 
  MenuItem,
  Button,
  Typography,
  Card,
  CardContent,
  Grid,
  LinearProgress
} from '@mui/material';
import { LineChart } from '@mui/x-charts';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider, DateTimePicker } from '@mui/x-date-pickers';

interface Player {
  player_id: string;
  name: string;
  teamName: string;
}

interface AnalyticsData {
  speeds: {
    data: number[];
    timestamps: number[];
    average: number;
    max: number;
  };
  steps: {
    count: number;
    timestamps: number[];
    magnitudes: number[];
  };
  jumps: {
    count: number;
    timestamps: number[];
    magnitudes: number[];
  };
  acceleration_magnitude: {
    data: number[];
    timestamps: number[];
  };
}

function App() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedPlayer, setSelectedPlayer] = useState('');
  const [startTime, setStartTime] = useState<Date | null>(null);
  const [endTime, setEndTime] = useState<Date | null>(null);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [timeRange, setTimeRange] = useState<{ start: Date | null; end: Date | null }>({ start: null, end: null });

  useEffect(() => {
    fetch('http://localhost:5001/api/players')
      .then(res => res.json())
      .then(data => setPlayers(data));
  }, []);

  useEffect(() => {
    if (selectedPlayer) {
      fetch(`http://localhost:5001/api/player-time-range?player_id=${selectedPlayer}`)
        .then(res => res.json())
        .then(data => {
          if (data.length > 0) {
            const range = data[0];
            const start = new Date(range.start_time / 1000);
            const end = new Date(range.end_time / 1000);
            setStartTime(start);
            setEndTime(end);
            setTimeRange({ start, end });
          }
        });
    }
  }, [selectedPlayer]);

  const handleAnalyze = () => {
    if (!selectedPlayer || !startTime || !endTime) return;

    setLoading(true);
    setProgress(0);

    const startMicros = startTime.getTime() * 1000;
    const endMicros = endTime.getTime() * 1000;

    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + 10; // Simulate progress
      });
    }, 1000); // Update every second

    fetch(`http://localhost:5001/api/player-analytics?player_id=${selectedPlayer}&start_time=${startMicros}&end_time=${endMicros}`)
      .then(res => res.json())
      .then(data => {
        setAnalyticsData(data);
        setLoading(false);
        clearInterval(interval);
      })
      .catch(() => {
        setLoading(false);
        clearInterval(interval);
      });
  };

  const generateCSV = () => {
    if (!analyticsData || !selectedPlayer) return;

    const player = players.find(p => p.player_id === selectedPlayer);
    const name = player ? player.name : 'Unknown';
    const teamName = player ? player.teamName : 'Unknown';
    const filename = `${name}_${teamName}_report.csv`;

    const csvData = [
      ['Metric', 'Value'],
      ['Steps Count', analyticsData.steps.count],
      ['Jumps Count', analyticsData.jumps.count],
      ['Max Speed (m/s)', analyticsData.speeds.max.toFixed(2)],
      ['Average Speed (m/s)', analyticsData.speeds.average.toFixed(2)],
    ];

    analyticsData.steps.timestamps.forEach((timestamp, index) => {
      csvData.push([
        `Step ${index + 1}`,
        `${new Date(timestamp / 1000).toLocaleString()}, Magnitude: ${analyticsData.steps.magnitudes[index]}`
      ]);
    });

    analyticsData.jumps.timestamps.forEach((timestamp, index) => {
      csvData.push([
        `Jump ${index + 1}`,
        `${new Date(timestamp / 1000).toLocaleString()}, Magnitude: ${analyticsData.jumps.magnitudes[index]}`
      ]);
    });

    const csvContent = csvData.map(row => row.join(',')).join('\n');

    const downloadLink = document.createElement('a');
    downloadLink.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(csvContent));
    downloadLink.setAttribute('download', filename);
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Container maxWidth="lg">
        <Box sx={{ my: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h4" component="h1" gutterBottom>
            Player Analytics Dashboard
          </Typography>
          {analyticsData && (
            <Button variant="contained" onClick={generateCSV}>
              Export as CSV
            </Button>
          )}
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Player</InputLabel>
              <Select
                value={selectedPlayer}
                onChange={(e) => {
                  setSelectedPlayer(e.target.value);
                  setAnalyticsData(null);
                }}
              >
                {players.map(player => (
                  <MenuItem key={player.player_id} value={player.player_id}>
                    {player.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={4}>
            <DateTimePicker
              label="Start Time"
              value={startTime}
              onChange={(newValue) => setStartTime(newValue)}
              minDate={timeRange.start || undefined}
              maxDate={timeRange.end || undefined}
              disabled={!timeRange.start || !timeRange.end}
            />
          </Grid>

          <Grid item xs={12} md={4}>
            <DateTimePicker
              label="End Time"
              value={endTime}
              onChange={(newValue) => setEndTime(newValue)}
              minDate={timeRange.start || undefined}
              maxDate={timeRange.end || undefined}
              disabled={!timeRange.start || !timeRange.end}
            />
          </Grid>

          <Grid item xs={12}>
            <Button 
              variant="contained" 
              onClick={handleAnalyze}
              disabled={!selectedPlayer || !startTime || !endTime}
            >
              Analyze
            </Button>
          </Grid>
        </Grid>

        {loading && (
          <Box sx={{ mt: 4 }}>
            <LinearProgress variant="determinate" value={progress} />
            <Typography variant="body2" sx={{ mt: 1 }}>
              {progress < 100 ? `Processing... ETA: ${Math.round((100 - progress) * 0.1)} seconds` : 'Completed'}
            </Typography>
          </Box>
        )}

        {analyticsData && (
          <Box sx={{ mt: 4 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant="h6">Steps Count</Typography>
                    <Typography variant="h4">{analyticsData.steps.count}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant="h6">Jumps Count</Typography>
                    <Typography variant="h4">{analyticsData.jumps.count}</Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={4}>
                <Card>
                  <CardContent>
                    <Typography variant="h6">Max Speed</Typography>
                    <Typography variant="h4">
                      {analyticsData.speeds.max.toFixed(2)} m/s
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12}>
                <Card>
                  <CardContent>
                    <Typography variant="h6">Acceleration Magnitude and Instantaneous Speed Over Time</Typography>
                    {analyticsData && (
                      <LineChart
                        xAxis={[{ 
                          data: analyticsData.acceleration_magnitude.timestamps.map(t => new Date(t / 1000))
                        }]}
                        series={[
                          {
                            data: analyticsData.acceleration_magnitude.data,
                            label: 'Acceleration Magnitude (m/s²)',
                            color: 'orange'
                          },
                          {
                            data: analyticsData.speeds.data,
                            label: 'Instantaneous Speed (m/s)',
                            color: 'blue'
                          }
                        ]}
                        height={400}
                      />
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        )}
      </Container>
    </LocalizationProvider>
  );
}

export default App;