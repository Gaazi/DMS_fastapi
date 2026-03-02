tailwind.config = {
    theme: {
        extend: {
            colors: {
                brand: {
                    50: '#f0f9ff',
                    100: '#e0f2fe',
                    500: '#0ea5e9',
                    600: '#0284c7',
                    700: '#0369a1',
                    800: '#075985',
                    900: '#0c4a6e',
                },
            },
            fontFamily: {
                nastaliq: ['Mehr', 'serif'],
                urdu: ['Mehr', 'serif'],
                mehr: ['Mehr', 'serif'],
                kufi: ['Reem Kufi Ink', 'sans-serif'],
                ruqaa: ['Aref Ruqaa Ink', 'serif'],
                amiri: ['Amiri', 'serif'],
                arabic: ['Amiri', 'serif'],
            },
            boxShadow: {
                'soft': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
                'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
            }
        },
    },
};
