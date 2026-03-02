from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import SignupForm


# Register view
def signup(request):                
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful! You can now log in.")  # Success message
            return redirect('login')  # Redirect to login page after successful registration
        else:
            messages.error(request, "There were errors in your form. Please check and try again.")  # Error message
    else:
        form = SignupForm()

    return render(request, 'signup.html', {'form': form})