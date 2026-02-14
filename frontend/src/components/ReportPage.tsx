import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reports, setReports] = useState<any[]>(null);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    const userId = keycloak.tokenParsed?.sub;
    if (!userId) {
      setError('User ID not found');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/reports?user_id=${userId}`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setReports(data.reports);

      // Download as CSV
      const csv = convertToCSV(data.reports);
      downloadCSV(csv, `reports_${userId}.csv`);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const convertToCSV = (data: any[]) => {
    if (!data || data.length === 0) return '';

    const headers = Object.keys(data[0]).join(',');
    const rows = data.map(row => Object.values(row).join(','));
    return [headers, ...rows].join('\n');
  };

  const downloadCSV = (csv: string, filename: string) => {
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reports && (
          <div className="mt-6">
            <h2 className="text-lg font-semibold mb-3">Report Preview</h2>
            <div className="max-h-64 overflow-y-auto border rounded">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-2 py-1 text-left">Date</th>
                    <th className="px-2 py-1 text-left">Device</th>
                    <th className="px-2 py-1 text-left">Signals</th>
                    <th className="px-2 py-1 text-left">Avg Response</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.slice(0, 10).map((report, index) => (
                    <tr key={index} className="border-t">
                      <td className="px-2 py-1">{report.report_date}</td>
                      <td className="px-2 py-1">{report.device_id}</td>
                      <td className="px-2 py-1">{report.total_signals}</td>
                      <td className="px-2 py-1">{report.avg_response_time.toFixed(2)}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {reports.length > 10 && (
                <div className="p-2 text-gray-500 text-center">
                  ... and {reports.length - 10} more rows
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
