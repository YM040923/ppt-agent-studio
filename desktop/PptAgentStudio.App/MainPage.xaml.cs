using Microsoft.UI.Xaml.Controls;
using PptAgentStudio_App.ViewModels;
using System;

// To learn more about WinUI, the WinUI project structure,
// and more about our project templates, see: http://aka.ms/winui-project-info.

namespace PptAgentStudio_App;

/// <summary>
/// The main content page displayed inside the application window.
/// </summary>
public sealed partial class MainPage : Page
{
    public MainPageViewModel ViewModel { get; } = new();

    public MainPage()
    {
        InitializeComponent();
    }

    private async void Page_Loaded(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        try
        {
            await PreviewWebView.EnsureCoreWebView2Async();
            PreviewWebView.NavigateToString(ViewModel.PreviewHtml);
            ViewModel.SessionStatus = "Preview pane ready. Local Agent runtime not connected.";
        }
        catch (Exception ex)
        {
            ViewModel.SessionStatus = $"Preview unavailable: {ex.Message}";
        }
    }
}
