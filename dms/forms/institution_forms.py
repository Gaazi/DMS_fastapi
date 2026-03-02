from django import forms
from ..models import Institution

class InstitutionCreationForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ['name', 'name_in_urdu', 'type', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors',
                'placeholder': 'Institution Name (English)'
            }),
            'name_in_urdu': forms.TextInput(attrs={
                'class': 'w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors',
                'placeholder': 'ادارے کا نام (مثلاً: جامعہ عمر فاروق)'
            }),
            'type': forms.Select(attrs={
                'class': 'w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition-colors appearance-none'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors',
                'placeholder': 'موبائل نمبر'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors resize-none h-24',
                'placeholder': 'ادارے کا مکمل پتہ',
                'rows': 3
            }),
        }
        labels = {
            'name': 'ادارے کا نام (English)',
            'name_in_urdu': 'ادارے کا نام (اردو)',
            'type': 'ادارے کی قسم',
            'phone': 'موبائل نمبر',
            'address': 'پتہ',
        }
