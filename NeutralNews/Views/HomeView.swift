//
//  ContentView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct HomeView: View {
    @State private var vm = ViewModel()
    @State private var date: Date = Date.now
    
    @Namespace private var animationNamespace
    
    var body: some View {
        NavigationStack {
            ScrollView {
                if !vm.searchText.isEmpty && vm.newsToShow.isEmpty && !vm.isLoadingNeutralNews {
                    noResultsView
                } else if vm.searchText.isEmpty && vm.newsToShow.isEmpty && !vm.isLoadingNeutralNews {
                    noNewsYetView
                } else {
                    LazyVStack {
                        ForEach(vm.newsToShow) { neutralNews in
                            NavigationLink {
                                NeutralNewsView(news: neutralNews, relatedNews: vm.getRelatedNews(from: neutralNews), namespace: animationNamespace)
                                    .navigationTransition(.zoom(sourceID: neutralNews.id, in: animationNamespace))
                            } label: {
                                NewsImageView(news: neutralNews, imageUrl: neutralNews.imageUrl)
                                    .padding(.vertical, 4)
                                    .matchedTransitionSource(id: neutralNews.id, in: animationNamespace)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal)
                }
                
                if vm.isLoadingNeutralNews {
                    VStack {
                        Spacer()
                        ProgressView()
                            .scaleEffect(2)
                        Spacer()
                    }
                    .frame(minHeight: UIScreen.main.bounds.height - 250)
                }
            }
            .scrollBounceBehavior(.basedOnSize)
            .refreshable {
                vm.fetchNeutralNewsFromFirestore()
                vm.fetchNewsFromFirestore()
            }
            .searchable(text: $vm.searchText, prompt: "Buscar")
            .navigationTitle(vm.daySelected.dayName)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { dayMenu }
                ToolbarItem(placement: .topBarTrailing) { filterMenu }
            }
        }
    }
    
    var dayMenu: some View {
        Menu {
            ForEach(vm.lastSevenDays) { day in
                Button(day.dayName) {
                    vm.changeDay(to: day)
                }

            }
        } label: {
            Label("Cambiar día", systemImage: "calendar")
        }
    }
    
    var filterMenu: some View {
        Menu {
            Menu("Relevancia") {
                ForEach(Relevance.allCases, id: \.self) { relevance in
                    Button {
                        vm.filterByRelevance(relevance)
                    } label: {
                        Label {
                            Text(relevance.description)
                        } icon: {
                            if vm.relevanceFilter.contains(relevance) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                    
                }
            }
            Menu("Categoria") {
                ForEach(Category.allCases, id: \.self) { category in
                    Button {
                        vm.filterByCategory(category)
                    } label: {
                        Label {
                            Label(category.rawValue, systemImage: category.systemImageName)
                        } icon: {
                            if vm.categoryFilter.contains(category) {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            }
            
            if vm.isAnyFilterEnabled {
                Section {
                    Button("Limpiar Filtros", role: .destructive) {
                        vm.clearFilters()
                    }
                }
            }
        } label: {
            Label("Filtrar", systemImage: vm.isAnyFilterEnabled ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
        }
    }
    
    var noResultsView: some View {
        VStack {
            Spacer()
            ContentUnavailableView(
                "No hay resultados para \"\(vm.searchText)\" en noticias de \(vm.daySelected.dayName)",
                systemImage: "magnifyingglass",
                description: Text("Prueba con otra búsqueda o selecciona otro día.")
            )
            Spacer()
        }
        .frame(minHeight: UIScreen.main.bounds.height - 200)
    }
    
    var noNewsYetView: some View {
        VStack {
            Spacer()
            ContentUnavailableView(
                "No hay noticias de \(vm.daySelected.dayName) aún",
                systemImage: "newspaper",
                description: Text("Prueba en unos minutos o selecciona otro día.")
            )
            Spacer()
        }
        .frame(minHeight: UIScreen.main.bounds.height - 300)
    }
}

#Preview {
    HomeView()
}
