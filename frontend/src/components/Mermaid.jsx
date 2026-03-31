import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

// Initialize mermaid configuration
mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
        primaryColor: '#f1f5f9',
        primaryTextColor: '#1e293b',
        primaryBorderColor: '#cbd5e1',
        lineColor: '#64748b',
        secondaryColor: '#e2e8f0',
        tertiaryColor: '#ffffff'
    },
    securityLevel: 'loose',
});

/**
 * Mermaid component renders Mermaid diagrams from a given chart definition string.
 * It includes sanitization logic to handle common issues and ensure proper rendering.
 *
 * @param {Object} props - The component props.
 * @param {string} props.chart - The Mermaid chart definition string.
 */
export const Mermaid = ({ chart }) => {
    const ref = useRef(null);
    const [renderId] = useState(() => `mermaid-${Math.random().toString(36).substring(2, 9)}`);

    /**
     * Sanitizes the Mermaid chart definition string to prevent rendering issues.
     * This includes removing markdown code blocks, hallucinatory blocks,
     * ensuring correct quoting for titles and labels, and removing illegal characters.
     *
     * @param {string} text - The raw Mermaid chart definition string.
     * @returns {string} The sanitized chart definition string.
     */
    const sanitizeChart = (text) => {
        if (!text) return "";
        let lines = text.trim().split('\n');
        let cleanLines = [];

        // Remove any markdown code blocks if they leaked into the string
        lines = lines.filter(l => !l.startsWith('```'));

        for (let line of lines) {
            let cleanLine = line.trim();
            if (!cleanLine) continue;

            // Remove hallucinatory blocks like { type categ }
            cleanLine = cleanLine.replace(/\{[^{}]*(type|categ|direction|theme)[^{}]*\}/gi, "");

            // Pie chart specific sanitization
            if (cleanLines.length > 0 && cleanLines[0].toLowerCase().startsWith('pie')) {
                if (cleanLine.includes(':')) {
                    const parts = cleanLine.split(':');
                    const label = parts[0].trim().replace(/[^a-zA-Z0-9\s]/g, ''); // Clean labels
                    const valueMatch = parts[1].trim().match(/^(\d+(\.\d+)?)/);
                    if (valueMatch) {
                        cleanLine = `"${label}" : ${valueMatch[1]}`;
                    }
                }
            }

            // Ensure titles are quoted correctly for v11
            if (cleanLine.toLowerCase().startsWith('title ')) {
                const titleText = cleanLine.substring(6).trim();
                const sanitizedTitle = titleText.replace(/"/g, '').replace(/'/g, '');
                cleanLine = `title "${sanitizedTitle}"`;
            }

            // Remove illegal characters from node labels in flowcharts
            if (cleanLine.includes('[') && cleanLine.includes(']')) {
                cleanLine = cleanLine.replace(/\[([^\]]*)\]/g, (match, content) => {
                    return `["${content.replace(/"/g, '')}"]`;
                });
            }

            // Remove any trailing semicolons or illegal punctuation
            cleanLine = cleanLine.replace(/[;]$/, '').trim();

            if (cleanLine) cleanLines.push(cleanLine);
        }

        return cleanLines.join('\n');
    };

    useEffect(() => {
        const renderChart = async () => {
            if (!ref.current || !chart) return;
            
            const cleanChart = sanitizeChart(chart);

            try {
                // Check if the chart is valid before attempting to render (prevents some v11 crashes)
                if (await mermaid.parse(cleanChart)) {
                    const { svg } = await mermaid.render(renderId, cleanChart);
                    if (ref.current) {
                        ref.current.innerHTML = svg;
                        ref.current.style.display = 'block';
                    }
                }
            } catch (err) {
                console.error("Mermaid Render Failed:", err);
                if (ref.current) {
                    ref.current.style.display = 'none'; // Gracefully hide on error
                }
            }
        };

        renderChart();
    }, [chart, renderId]);

    return (
        <div 
            ref={ref} 
            className="mermaid-chart flex justify-center my-6 overflow-x-auto bg-slate-50 border border-slate-200 p-6 rounded-2xl transition-all" 
            style={{ display: 'none' }} // Hidden by default until success
        />
    );
};