using Microsoft.UI.Xaml.Controls;
using Microsoft.Web.WebView2.Core;
using PptAgentStudio_App.Services;
using PptAgentStudio_App.ViewModels;
using System;
using System.ComponentModel;
using System.Globalization;

// To learn more about WinUI, the WinUI project structure,
// and more about our project templates, see: http://aka.ms/winui-project-info.

namespace PptAgentStudio_App;

/// <summary>
/// The main content page displayed inside the application window.
/// </summary>
public sealed partial class MainPage : Page
{
    public MainPageViewModel ViewModel { get; } = new();

    private readonly PreviewPaneState _previewPaneState = new();
    private bool _previewScriptReady;

    public MainPage()
    {
        InitializeComponent();
        ViewModel.PropertyChanged += OnViewModelPropertyChanged;
        UpdatePreviewToolbar();
    }

    private async void Page_Loaded(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        try
        {
            await PreviewWebView.EnsureCoreWebView2Async();
            PreviewWebView.NavigateToString(ViewModel.PreviewHtml);
            await ViewModel.InitializeRuntimeAsync();
        }
        catch (Exception ex)
        {
            ViewModel.SessionStatus = $"Preview unavailable: {ex.Message}";
        }
    }

    private void Page_Unloaded(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        ViewModel.StopRuntime();
    }

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(ViewModel.PreviewHtml) && PreviewWebView.CoreWebView2 is not null)
        {
            _previewScriptReady = false;
            _previewPaneState.ResetSlidePosition();
            UpdatePreviewToolbar();
            PreviewWebView.NavigateToString(ViewModel.PreviewHtml);
        }
    }

    private async void PreviewWebView_NavigationCompleted(WebView2 sender, CoreWebView2NavigationCompletedEventArgs args)
    {
        if (!args.IsSuccess)
        {
            return;
        }

        await InitializePreviewInteractionAsync();
    }

    private async void PreviewPrevious_Click(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        _previewPaneState.GoPrevious();
        await ApplyPreviewStateAsync();
    }

    private async void PreviewNext_Click(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        _previewPaneState.GoNext();
        await ApplyPreviewStateAsync();
    }

    private async void PreviewZoomOut_Click(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        _previewPaneState.ZoomOut();
        await ApplyPreviewStateAsync();
    }

    private async void PreviewZoomReset_Click(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        _previewPaneState.ResetZoom();
        await ApplyPreviewStateAsync();
    }

    private async void PreviewZoomIn_Click(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        _previewPaneState.ZoomIn();
        await ApplyPreviewStateAsync();
    }

    private async void Settings_Click(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        var dialog = new ContentDialog
        {
            XamlRoot = XamlRoot,
            Title = "Runtime Settings",
            Content = ViewModel.SettingsText,
            CloseButtonText = "Close"
        };
        await dialog.ShowAsync();
    }

    private void ChatMessageAction_Click(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        if (sender is Button { Tag: "open_pptx" } && ViewModel.ExportLatestCommand.CanExecute(null))
        {
            ViewModel.ExportLatestCommand.Execute(null);
        }
        else if (sender is Button { Tag: "demo_deck" } && ViewModel.GenerateDemoCommand.CanExecute(null))
        {
            ViewModel.GenerateDemoCommand.Execute(null);
        }
    }

    private async Task InitializePreviewInteractionAsync()
    {
        if (PreviewWebView.CoreWebView2 is null)
        {
            return;
        }

        var slideCountJson = await PreviewWebView.ExecuteScriptAsync(PreviewInteractionScripts.Initialize);
        _previewPaneState.SetSlideCount(ParseScriptInt(slideCountJson));
        _previewScriptReady = true;
        await ApplyPreviewStateAsync();
    }

    private async Task ApplyPreviewStateAsync()
    {
        UpdatePreviewToolbar();
        if (!_previewScriptReady || PreviewWebView.CoreWebView2 is null)
        {
            return;
        }

        var zoom = (_previewPaneState.ZoomPercent / 100d).ToString(CultureInfo.InvariantCulture);
        await PreviewWebView.ExecuteScriptAsync(
            $"window.pptAgentPreview?.showSlide({_previewPaneState.CurrentSlideIndex});" +
            $"window.pptAgentPreview?.setZoom({zoom});");
        UpdatePreviewToolbar();
    }

    private void UpdatePreviewToolbar()
    {
        PreviewPageText.Text = _previewPaneState.PageText;
        PreviewZoomText.Text = _previewPaneState.ZoomText;
        PreviewPreviousButton.IsEnabled = _previewScriptReady && _previewPaneState.CanGoPrevious;
        PreviewNextButton.IsEnabled = _previewScriptReady && _previewPaneState.CanGoNext;
        PreviewZoomOutButton.IsEnabled = _previewScriptReady && _previewPaneState.ZoomPercent > 50;
        PreviewZoomResetButton.IsEnabled = _previewScriptReady && _previewPaneState.ZoomPercent != 100;
        PreviewZoomInButton.IsEnabled = _previewScriptReady && _previewPaneState.ZoomPercent < 200;
    }

    private static int ParseScriptInt(string? json)
    {
        return int.TryParse(json?.Trim('"'), NumberStyles.Integer, CultureInfo.InvariantCulture, out var value)
            ? value
            : 0;
    }
}
